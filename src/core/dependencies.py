"""
Authentication and Tenant Dependencies
"""

import logging
import os
import time
from typing import Any, Dict, Optional

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

# JWT Configuration
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
JWKS_URL = f"{AUTH_SERVICE_URL}/.well-known/jwks.json"
JWKS_CACHE_TTL = int(os.getenv("JWKS_CACHE_TTL", "3600"))  # Cache for 1 hour

# Cache JWKS client
_jwks_client: Optional[PyJWKClient] = None
_jwks_client_initialized = False
_last_fetch_attempt = 0


def get_jwks_client() -> Optional[PyJWKClient]:
    """Get or create JWKS client with caching and retry logic"""
    global _jwks_client, _jwks_client_initialized, _last_fetch_attempt

    # If already initialized, return the client (even if None)
    if _jwks_client_initialized:
        return _jwks_client

    # Don't retry more than once every 30 seconds
    current_time = time.time()
    if _last_fetch_attempt > 0 and (current_time - _last_fetch_attempt) < 30:
        logger.warning("⏳ JWKS fetch recently attempted, using cached result")
        return _jwks_client

    _last_fetch_attempt = current_time

    try:
        # First, verify the JWKS endpoint is accessible
        logger.info(f"🔍 Checking JWKS endpoint: {JWKS_URL}")
        response = requests.get(JWKS_URL, timeout=5)

        if response.status_code != 200:
            logger.error(f"❌ JWKS endpoint returned {response.status_code}")
            _jwks_client = None
            _jwks_client_initialized = True
            return None

        # Log the keys found
        jwks_data = response.json()
        key_count = len(jwks_data.get("keys", []))
        logger.info(f"✅ JWKS endpoint accessible, found {key_count} key(s)")

        # Initialize the JWKS client
        _jwks_client = PyJWKClient(JWKS_URL)
        _jwks_client_initialized = True
        logger.info(f"✅ JWKS client initialized from {JWKS_URL}")

        return _jwks_client

    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Cannot connect to Auth Service at {AUTH_SERVICE_URL}: {e}")
        _jwks_client = None
        _jwks_client_initialized = True
        return None

    except requests.exceptions.Timeout as e:
        logger.error(f"❌ Connection timeout to Auth Service: {e}")
        _jwks_client = None
        _jwks_client_initialized = True
        return None

    except Exception as e:
        logger.error(f"❌ Failed to initialize JWKS client: {e}")
        _jwks_client = None
        _jwks_client_initialized = True
        return None


def verify_rs256_token(token: str) -> Dict[str, Any]:
    """Verify RS256 token using JWKS"""
    client = get_jwks_client()

    if not client:
        logger.error("❌ JWKS client is not available")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable. Please try again later.",
        )

    try:
        # Get signing key
        signing_key = client.get_signing_key_from_jwt(token)
        logger.debug(f"✅ Retrieved signing key with kid: {signing_key.key_id}")

        # Verify token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_exp": True,
                "verify_aud": False,  # Set to True if you have audience validation
            },
        )

        logger.debug(f"✅ RS256 token verified for user: {payload.get('sub')}")
        return payload

    except jwt.ExpiredSignatureError:
        logger.warning("❌ Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"❌ RS256 token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except PyJWKClientError as e:
        logger.error(f"❌ JWKS client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to verify authentication. Please try again.",
        )


def verify_hs256_token(token: str) -> Dict[str, Any]:
    """Fallback: Verify HS256 token using shared secret"""
    secret_key = os.getenv("JWT_SECRET_KEY", "your-secret-key")

    try:
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=["HS256"],
            options={"verify_exp": True},
        )
        logger.debug(f"✅ HS256 token verified for user: {payload.get('sub')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("❌ HS256 token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"❌ HS256 token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Extract tenant_id from JWT token.

    Production: Uses RS256 with JWKS from Auth Service
    Development: Can bypass with DEV_SKIP_JWT_VERIFICATION=true
    """
    # Check if credentials were provided
    if not credentials:
        logger.warning("❌ No credentials provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated - missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    logger.debug(f"Received token: {token[:50]}...")

    # Development bypass (for local testing only)
    if os.getenv("DEV_SKIP_JWT_VERIFICATION", "false").lower() == "true":
        logger.warning("⚠️ DEVELOPMENT MODE: JWT verification disabled")
        dev_tenant = os.getenv("DEV_TENANT_ID", "test-tenant-123")
        return {
            "tenant_id": dev_tenant,
            "user_id": "dev-user",
            "role": "admin",
            "email": "dev@example.com",
        }

    # Production: Verify RS256 token
    try:
        logger.info("🔍 Attempting RS256 token verification with JWKS...")
        payload = verify_rs256_token(token)
        logger.info("✅ Token verified with RS256")

    except HTTPException as e:
        # If RS256 fails and fallback is allowed, try HS256
        if os.getenv("ALLOW_HS256_FALLBACK", "false").lower() == "true":
            logger.warning(f"RS256 failed: {e.detail}. Attempting HS256 fallback...")
            try:
                payload = verify_hs256_token(token)
                logger.info("✅ Token verified with HS256 fallback")
            except HTTPException as fallback_error:
                logger.error(f"HS256 fallback also failed: {fallback_error.detail}")
                raise
        else:
            logger.error(f"RS256 verification failed and HS256 fallback is disabled")
            raise

    # Extract tenant_id
    tenant_id = payload.get("tenant_id")
    if not tenant_id:
        logger.error("❌ Token missing tenant_id claim")
        logger.debug(f"Available claims in token: {list(payload.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Missing tenant ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Extract user info
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        logger.warning("⚠️ Token missing user identifier (sub or user_id claim)")

    logger.info(f"🔐 Authenticated: user={user_id}, tenant={tenant_id}")

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": payload.get("role", "user"),
        "email": payload.get("email"),
        "permissions": payload.get("permissions", []),
    }

"""
Authentication and Tenant Dependencies
"""

import logging
import os
from typing import Any, Dict

import jwt
import requests
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient, PyJWKClientError

logger = logging.getLogger(__name__)
security = HTTPBearer()

# JWT Configuration
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
JWKS_URL = f"{AUTH_SERVICE_URL}/.well-known/jwks.json"
JWKS_CACHE_TTL = int(os.getenv("JWKS_CACHE_TTL", "3600"))  # Cache for 1 hour

# Cache JWKS client
_jwks_client = None
_jwks_client_initialized = False


def get_jwks_client() -> PyJWKClient:
    """Get or create JWKS client with caching"""
    global _jwks_client, _jwks_client_initialized

    if not _jwks_client_initialized:
        try:
            # First, verify the JWKS endpoint is accessible
            logger.info(f"🔍 Checking JWKS endpoint: {JWKS_URL}")
            response = requests.get(JWKS_URL, timeout=5)

            if response.status_code != 200:
                logger.error(f"JWKS endpoint returned {response.status_code}")
                _jwks_client = None
            else:
                # Log the keys found (without exposing full key)
                jwks_data = response.json()
                key_count = len(jwks_data.get("keys", []))
                logger.info(f"✅ JWKS endpoint accessible, found {key_count} key(s)")

                # Initialize the JWKS client
                _jwks_client = PyJWKClient(JWKS_URL)
                logger.info(f"✅ JWKS client initialized from {JWKS_URL}")

        except requests.exceptions.ConnectionError as e:
            logger.error(
                f"❌ Cannot connect to Auth Service at {AUTH_SERVICE_URL}: {e}"
            )
            _jwks_client = None
        except requests.exceptions.Timeout as e:
            logger.error(f"❌ Connection timeout to Auth Service: {e}")
            _jwks_client = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize JWKS client: {e}")
            _jwks_client = None
        finally:
            _jwks_client_initialized = True

    return _jwks_client


def verify_rs256_token(token: str) -> Dict[str, Any]:
    """Verify RS256 token using JWKS"""
    client = get_jwks_client()

    if not client:
        logger.error("JWKS client is not available - cannot verify RS256 token")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        logger.warning("Token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please login again.",
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"RS256 token validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {str(e)}"
        )
    except PyJWKClientError as e:
        logger.error(f"JWKS client error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
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
        logger.warning("HS256 token has expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.error(f"HS256 token validation failed: {e}")
        raise


def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> Dict[str, Any]:
    """
    Extract tenant_id from JWT token.

    Production: Uses RS256 with JWKS from Auth Service
    Development: Can bypass with DEV_SKIP_JWT_VERIFICATION=true
    """
    token = credentials.credentials
    logger.debug(f"Received token: {token[:50]}...")  # Log first 50 chars only

    # Development bypass
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
        # First, try RS256 with JWKS (recommended)
        logger.info("Attempting RS256 token verification with JWKS...")
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
        logger.error("Token missing tenant_id claim")
        logger.debug(f"Available claims in token: {list(payload.keys())}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: Missing tenant ID",
        )

    # Extract user info
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        logger.warning("Token missing user identifier (sub or user_id claim)")

    logger.info(f"🔐 Authenticated: user={user_id}, tenant={tenant_id}")

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "role": payload.get("role", "user"),
        "email": payload.get("email"),
        "permissions": payload.get("permissions", []),
    }

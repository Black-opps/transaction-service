"""
Database session management with connection pooling and retry logic
"""

import logging
import os
from contextlib import contextmanager
from typing import Generator, Optional

from dotenv import load_dotenv
from sqlalchemy import create_engine, event, text  # ADD text here
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DisconnectionError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import QueuePool

load_dotenv()

logger = logging.getLogger(__name__)

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")

# Pool configuration
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 20))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 40))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", 30))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", 3600))
POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
ECHO_SQL = os.getenv("DB_ECHO", "false").lower() == "true"

# Create engine with optimized settings
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=POOL_SIZE,
    max_overflow=MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,
    echo=ECHO_SQL,
    # Performance optimizations
    connect_args={
        "options": "-c timezone=utc -c statement_timeout=30000",
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    },
)


@event.listens_for(engine, "connect")
def connect(dbapi_connection, connection_record):
    """Set connection-specific settings"""
    cursor = dbapi_connection.cursor()
    cursor.execute("SET timezone = 'UTC'")
    cursor.execute("SET statement_timeout = '30000'")  # 30 seconds
    cursor.close()


@event.listens_for(engine, "checkout")
def checkout(dbapi_connection, connection_record, connection_proxy):
    """Log connection checkout for debugging"""
    logger.debug(f"Connection checked out from pool")


# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,  # Prevent expired object errors
)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI routes with automatic retry on disconnection
    """
    max_retries = 3
    retry_count = 0

    while retry_count < max_retries:
        db = SessionLocal()
        try:
            # Test connection - FIXED: Use text() for SQLAlchemy 2.x
            db.execute(text("SELECT 1"))
            yield db
            db.commit()
            break
        except DisconnectionError:
            db.rollback()
            retry_count += 1
            logger.warning(f"Database disconnected, retry {retry_count}/{max_retries}")
            if retry_count == max_retries:
                raise
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


@contextmanager
def get_db_context() -> Generator[Session, None, None]:
    """Context manager for manual database sessions"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_engine_status() -> dict:
    """Get database connection pool status"""
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "overflow": pool.overflow(),
        "total": pool.total(),
        "max_connections": POOL_SIZE + MAX_OVERFLOW,
    }

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Centralized configuration management"""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL")

    # Service
    SERVICE_NAME: str = "transaction-service"
    PORT: int = int(os.getenv("PORT", 8006))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Business rules
    MAX_TRANSACTIONS_PER_BATCH: int = 1000
    DEFAULT_PAGE_LIMIT: int = 100
    MAX_PAGE_LIMIT: int = 1000


settings = Settings()

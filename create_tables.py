# create_tables.py
import os
import sys

# Add the current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from src.database.base import Base
from src.database.session import engine
from src.models.transaction import Transaction


def create_tables():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created successfully!")


if __name__ == "__main__":
    create_tables()

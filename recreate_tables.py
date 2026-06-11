# recreate_tables.py
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from src.database.base import Base
from src.database.session import engine
from src.models.transaction import Transaction


def recreate_tables():
    print("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    print("✅ Tables dropped!")

    print("Creating tables with new schema...")
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created with category, merchant, source, tags columns!")


if __name__ == "__main__":
    recreate_tables()

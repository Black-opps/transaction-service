# add_columns.py
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from src.database.session import engine


def add_missing_columns():
    with engine.connect() as conn:
        # Add category column
        try:
            conn.execute(
                text("ALTER TABLE transactions ADD COLUMN category VARCHAR(100)")
            )
            print("✅ Added category column")
        except Exception as e:
            print(f"Category column may already exist: {e}")

        # Add merchant column
        try:
            conn.execute(
                text("ALTER TABLE transactions ADD COLUMN merchant VARCHAR(255)")
            )
            print("✅ Added merchant column")
        except Exception as e:
            print(f"Merchant column may already exist: {e}")

        # Add source column
        try:
            conn.execute(
                text(
                    "ALTER TABLE transactions ADD COLUMN source VARCHAR(50) DEFAULT 'mpesa'"
                )
            )
            print("✅ Added source column")
        except Exception as e:
            print(f"Source column may already exist: {e}")

        # Add tags column (JSON)
        try:
            conn.execute(text("ALTER TABLE transactions ADD COLUMN tags JSON"))
            print("✅ Added tags column")
        except Exception as e:
            print(f"Tags column may already exist: {e}")

        conn.commit()
        print("\n✅ All columns added successfully!")


if __name__ == "__main__":
    add_missing_columns()

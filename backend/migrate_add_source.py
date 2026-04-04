"""Migration: add source column to feedback table.

Run once against an existing database to add the source column.
Safe to re-run — skips silently if the column already exists.

Usage:
    python backend/migrate_add_source.py
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "lost_world.db"


def migrate(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"Database not found at {db_path} — nothing to migrate.")
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Check if column already exists
        cursor.execute("PRAGMA table_info(feedback)")
        columns = [row[1] for row in cursor.fetchall()]
        if "source" in columns:
            print("Column 'source' already exists — skipping.")
            return

        cursor.execute(
            "ALTER TABLE feedback ADD COLUMN source VARCHAR(32) NOT NULL DEFAULT 'user'"
        )
        conn.commit()
        print(f"Added 'source' column to feedback table in {db_path}.")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()

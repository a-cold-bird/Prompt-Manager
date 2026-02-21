#!/usr/bin/env python3
"""
Migrate Prompt Manager data from SQLite to PostgreSQL.

Usage:
  python scripts/migrate_sqlite_to_postgres.py \
    --sqlite-path ./data/data.sqlite \
    --postgres-url postgresql+psycopg2://user:pass@host:5432/dbname \
    --force
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

from sqlalchemy import create_engine, text

# Ensure project root is importable when running script directly.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from extensions import db
import models  # noqa: F401  # Ensure models/tables are registered in metadata


INSERT_ORDER = [
    "user",
    "system_setting",
    "tag",
    "image",
    "image_tags",
    "reference_image",
]

DELETE_ORDER = list(reversed(INSERT_ORDER))

INDEX_SQL = [
    "CREATE INDEX IF NOT EXISTS ix_image_created_at ON image (created_at)",
    "CREATE INDEX IF NOT EXISTS ix_image_status_category_created_at ON image (status, category, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_image_status_category_heat_created_at ON image (status, category, heat_score, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_image_status_category_type_created_at ON image (status, category, type, created_at)",
    "CREATE INDEX IF NOT EXISTS ix_image_tags_image_id ON image_tags (image_id)",
    "CREATE INDEX IF NOT EXISTS ix_image_tags_tag_id ON image_tags (tag_id)",
    "CREATE INDEX IF NOT EXISTS ix_image_tags_tag_image ON image_tags (tag_id, image_id)",
    "CREATE INDEX IF NOT EXISTS ix_reference_image_image_id ON reference_image (image_id)",
    "CREATE INDEX IF NOT EXISTS ix_reference_image_image_position ON reference_image (image_id, position)",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate SQLite data to PostgreSQL.")
    parser.add_argument(
        "--sqlite-path",
        default="instance/data.sqlite",
        help="Path to source SQLite database file (default: instance/data.sqlite)",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Target PostgreSQL SQLAlchemy URL. Defaults to DATABASE_URL env.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Clear target tables before import.",
    )
    return parser.parse_args()


def fetch_sqlite_rows(conn: sqlite3.Connection, table_name: str) -> List[Dict[str, Any]]:
    try:
        cur = conn.execute(f"SELECT * FROM {table_name}")
    except sqlite3.OperationalError:
        return []

    columns = [col[0] for col in cur.description]
    rows = []
    for row in cur.fetchall():
        rows.append(dict(zip(columns, row)))
    return rows


def normalize_rows(table_name: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if table_name != "image":
        return rows

    for row in rows:
        created_at = row.get("created_at")
        if isinstance(created_at, str) and created_at:
            try:
                row["created_at"] = datetime.fromisoformat(created_at)
            except ValueError:
                # Keep original value if parsing fails.
                pass
    return rows


def validate_target_url(postgres_url: str) -> None:
    if not postgres_url:
        raise ValueError("Missing --postgres-url (or DATABASE_URL env).")
    if not postgres_url.startswith("postgresql"):
        raise ValueError(f"Target URL must be PostgreSQL, got: {postgres_url}")


def ensure_indexes(pg_engine) -> None:
    with pg_engine.begin() as conn:
        for stmt in INDEX_SQL:
            conn.execute(text(stmt))


def main() -> None:
    args = parse_args()
    sqlite_path = args.sqlite_path
    postgres_url = args.postgres_url

    validate_target_url(postgres_url)

    if not os.path.exists(sqlite_path):
        raise FileNotFoundError(f"SQLite file not found: {sqlite_path}")

    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    pg_engine = create_engine(postgres_url, future=True, pool_pre_ping=True)

    # Ensure all tables exist in target DB.
    db.metadata.create_all(bind=pg_engine)

    source_data: Dict[str, List[Dict[str, Any]]] = {}
    for table_name in INSERT_ORDER:
        rows = fetch_sqlite_rows(sqlite_conn, table_name)
        source_data[table_name] = normalize_rows(table_name, rows)

    with pg_engine.begin() as conn:
        # Safety check: avoid accidental merge unless explicitly forced.
        if not args.force:
            for table_name in INSERT_ORDER:
                table = db.metadata.tables[table_name]
                count = conn.execute(text(f"SELECT COUNT(*) FROM {table.name}")).scalar_one()
                if count > 0:
                    raise RuntimeError(
                        f"Target table '{table_name}' is not empty ({count} rows). "
                        f"Re-run with --force to replace target data."
                    )

        if args.force:
            for table_name in DELETE_ORDER:
                table = db.metadata.tables[table_name]
                conn.execute(table.delete())

        for table_name in INSERT_ORDER:
            table = db.metadata.tables[table_name]
            rows = source_data[table_name]
            if rows:
                conn.execute(table.insert(), rows)

    ensure_indexes(pg_engine)
    sqlite_conn.close()

    print("Migration completed.")
    for table_name in INSERT_ORDER:
        print(f"  - {table_name}: {len(source_data[table_name])} rows")
    print("Indexes ensured.")


if __name__ == "__main__":
    main()

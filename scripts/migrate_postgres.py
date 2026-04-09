from __future__ import annotations

import os
from pathlib import Path
import sys

import psycopg


def main() -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 1

    migrations_dir = Path("migrations")
    migration_files = sorted(path for path in migrations_dir.glob("*.sql") if not path.name.endswith(".down.sql"))

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cursor.execute("SELECT version FROM schema_migrations")
            applied = {row[0] for row in cursor.fetchall()}
            for migration_file in migration_files:
                if migration_file.name in applied:
                    continue
                cursor.execute(migration_file.read_text(encoding="utf-8"))
                cursor.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (migration_file.name,))
        connection.commit()

    print(f"Applied {len(migration_files)} migrations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

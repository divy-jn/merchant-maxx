import os
import psycopg2
from dotenv import load_dotenv

load_dotenv(".env")
DATABASE_URL = os.environ.get("DATABASE_URL")


def run_migrations():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is required")
    conn = psycopg2.connect(DATABASE_URL)
    try:
        conn.autocommit = True
        with conn.cursor() as cursor:
            with open("backend/db/schema.sql", "r", encoding="utf-8") as f:
                cursor.execute(f.read())
            import glob
            migrations = sorted(glob.glob("backend/db/migrations/*.sql"))
            for migration_path in migrations:
                try:
                    with open(migration_path, "r", encoding="utf-8") as f:
                        cursor.execute(f.read())
                except Exception as e:
                    print(f"Failed to run migration {migration_path}: {e}")
                    raise
        print("Schema and migrations applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()

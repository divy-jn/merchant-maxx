import os
import psycopg2

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
            migration_path = "backend/db/migrations/001_purchase_intents.sql"
            try:
                with open(migration_path, "r", encoding="utf-8") as f:
                    cursor.execute(f.read())
            except FileNotFoundError:
                pass
        print("Schema and migrations applied successfully.")
    finally:
        conn.close()


if __name__ == "__main__":
    run_migrations()

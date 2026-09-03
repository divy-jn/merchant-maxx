import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv(".env")

async def run_migration():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set")
        return

    # Use the session pooler if there's connection limit issue, but direct is fine.
    # The URL in .env is probably postgresql://postgres:postgres@localhost:54322/postgres
    
    with open("backend/db/migrations/007_payment_state_finality.sql", "r") as f:
        sql = f.read()

    try:
        conn = await asyncpg.connect(db_url)
        print("Executing migration 007...")
        await conn.execute(sql)
        print("Migration applied successfully.")
        await conn.close()
    except Exception as e:
        print(f"Failed to apply migration: {e}")

if __name__ == "__main__":
    asyncio.run(run_migration())

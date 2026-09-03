import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("c:/building projs/razorpay_proj/.env")

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found.")
    exit(1)

migration_file = "c:/building projs/razorpay_proj/backend/db/migrations/005_rls_hardening.sql"

try:
    with open(migration_file, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(sql)
    print("Migration applied successfully!")
except Exception as e:
    print(f"Failed: {e}")
finally:
    if 'conn' in locals() and conn:
        conn.close()

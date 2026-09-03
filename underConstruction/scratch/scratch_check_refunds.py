import os
import psycopg2
from dotenv import load_dotenv

load_dotenv("c:/building projs/razorpay_proj/.env")

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    print("No DATABASE_URL found.")
    exit(1)

try:
    conn = psycopg2.connect(db_url)
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'refunds';
        """)
        columns = cur.fetchall()
        print(f"Refunds table columns: {columns}")
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'conn' in locals() and conn:
        conn.close()

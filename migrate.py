import psycopg2
import os
from urllib.parse import urlparse

DATABASE_URL = "postgresql://postgres:[MASKED_DB_PASSWORD]@db.aynzhepktrvgtxqcdwdn.supabase.co:5432/postgres"

def run_migrations():
    try:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True
        cursor = conn.cursor()
        
        with open('backend/db/schema.sql', 'r') as f:
            sql = f.read()
            
        print("Running schema.sql...")
        cursor.execute(sql)
        print("Schema created successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    run_migrations()

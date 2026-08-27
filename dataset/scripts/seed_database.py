import os
import csv
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'synthetic')
DERIVED_DIR = os.path.join(BASE_DIR, 'data', 'derived')
PROJECT_ROOT = os.path.dirname(BASE_DIR)

load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Use Supavisor connection pooler for IPv4 compatibility
    # Original: postgresql://postgres:password@db.aynzhepktrvgtxqcdwdn.supabase.co:5432/postgres
    import urllib.parse
    parsed = urllib.parse.urlparse(db_url)
    password = parsed.password
    db_url = f"postgresql://postgres.aynzhepktrvgtxqcdwdn:{password}@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"

TABLES_TO_SEED = [
    # Table name, directory, file name
    ("products", SYNTHETIC_DIR, "products.csv"),
    ("customers", SYNTHETIC_DIR, "customers.csv"),
    ("orders", SYNTHETIC_DIR, "orders.csv"),
    ("order_items", SYNTHETIC_DIR, "order_items.csv"),
    ("payments", SYNTHETIC_DIR, "payments.csv"),
    ("refunds", SYNTHETIC_DIR, "refunds.csv"),
    ("customer_events", SYNTHETIC_DIR, "customer_events.csv"),
    ("product_affinity", DERIVED_DIR, "product_affinity.csv"),
    ("customer_metrics", DERIVED_DIR, "customer_metrics.csv"),
    ("campaigns", SYNTHETIC_DIR, "campaigns.csv"),
    ("recommendation_events", SYNTHETIC_DIR, "recommendation_events.csv"),
    ("agent_audit", SYNTHETIC_DIR, "agent_audit.csv")
]

def seed_table(conn, table_name, dir_path, file_name):
    print(f"\nSeeding {table_name}...")
    file_path = os.path.join(dir_path, file_name)
    
    if not os.path.exists(file_path):
        print(f"  Skipping {table_name}: file {file_name} not found.")
        return
        
    rows = []
    columns = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames
        for row in reader:
            if table_name == 'products':
                row['active'] = (row['active'] == 'True')
                if not row['inventory_qty']: row['inventory_qty'] = 0
            
            # Format row as tuple
            rows.append(tuple(row[col] if row[col] != '' else None for col in columns))
            
    if not rows:
        print(f"  {table_name} is empty.")
        return
        
    print(f"  Read {len(rows)} rows. Inserting...")
    
    insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES %s ON CONFLICT DO NOTHING;"
    
    try:
        with conn.cursor() as cur:
            execute_values(cur, insert_query, rows, page_size=1000)
        conn.commit()
        print(f"  Successfully inserted/merged rows for {table_name}.")
    except Exception as e:
        conn.rollback()
        print(f"  Error inserting {table_name}: {e}")

def run():
    print("Starting database seed...")
    try:
        conn = psycopg2.connect(db_url)
        
        print("Executing schema.sql...")
        schema_path = os.path.join(PROJECT_ROOT, 'backend', 'db', 'schema.sql')
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
        with conn.cursor() as cur:
            cur.execute(schema_sql)
        conn.commit()
        print("Schema applied.")
        
        for table_name, dir_path, file_name in TABLES_TO_SEED:
            seed_table(conn, table_name, dir_path, file_name)
        conn.close()
        print("\nDatabase seeding finished.")
    except Exception as e:
        print(f"Failed to connect or seed database: {e}")

if __name__ == "__main__":
    run()

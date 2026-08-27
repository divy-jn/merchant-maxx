import os
import csv
from dotenv import load_dotenv
from supabase import create_client, Client

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'synthetic')
DERIVED_DIR = os.path.join(BASE_DIR, 'data', 'derived')
PROJECT_ROOT = os.path.dirname(BASE_DIR)

load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("Warning: SUPABASE_URL or SUPABASE_SERVICE_KEY not found. Skipping seeding.")
    exit(0)

supabase: Client = create_client(url, key)

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

def seed_table(table_name, dir_path, file_name):
    print(f"\nSeeding {table_name}...")
    file_path = os.path.join(dir_path, file_name)
    
    if not os.path.exists(file_path):
        print(f"  Skipping {table_name}: file {file_name} not found.")
        return
        
    # Read rows
    rows = []
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Simple conversion for JSONB/Boolean fields where necessary
            if table_name == 'products':
                row['active'] = row['active'] == 'True'
                if not row['inventory_qty']: row['inventory_qty'] = 0
            
            rows.append(row)
            
    if not rows:
        print(f"  {table_name} is empty.")
        return
        
    print(f"  Read {len(rows)} rows. Inserting in batches of 500...")
    
    # We don't truncate by default to avoid destroying other data, 
    # but in a real pipeline we might want a clean slate option.
    
    batch_size = 500
    success = 0
    
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        try:
            supabase.table(table_name).insert(batch).execute()
            success += len(batch)
            print(f"  Inserted {success}/{len(rows)}")
        except Exception as e:
            print(f"  Error inserting batch {i//batch_size}: {e}")
            # we continue to try next batch

def run():
    print("Starting database seed...")
    for table_name, dir_path, file_name in TABLES_TO_SEED:
        seed_table(table_name, dir_path, file_name)
    print("\nDatabase seeding finished.")

if __name__ == "__main__":
    run()

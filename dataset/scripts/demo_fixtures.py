import os
import csv
import json
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'synthetic')
DERIVED_DIR = os.path.join(BASE_DIR, 'data', 'derived')

def append_to_csv(filepath, rows):
    if not rows: return
    file_exists = os.path.isfile(filepath)
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

def generate_fixtures():
    print("Injecting demo fixtures...")
    now = datetime.now().isoformat()
    
    # 1. Customer
    customer = {
        "customer_id": "cust_demo_001",
        "merchant_id": "merchant_mxx_001",
        "name": "Demo User",
        "email": "demo@merchantmaxx.test",
        "phone": "9876543210",
        "city": "Bengaluru",
        "state": "Karnataka",
        "segment": "VIP",
        "first_order_at": now,
        "last_order_at": now,
        "total_orders": 5,
        "total_spent_paise": 5000000,
        "created_at": now
    }
    
    # 2. Products
    product_base = {
        "product_id": "prod_demo_base",
        "merchant_id": "merchant_mxx_001",
        "name": "Sony Alpha ILCE-7RM4A Camera",
        "description": "High resolution full-frame mirrorless camera.",
        "category": "Electronics",
        "subcategory": "Cameras",
        "brand": "Sony",
        "price_paise": 25000000, # Rs 2,50,000
        "currency": "INR",
        "inventory_qty": 10,
        "active": True,
        "rating": 4.8,
        "tags": json.dumps(["photography", "professional"]),
        "created_at": now,
        "updated_at": now
    }
    
    product_upsell = {
        "product_id": "prod_demo_upsell",
        "merchant_id": "merchant_mxx_001",
        "name": "Sony FE 24-70mm f/2.8 GM Lens",
        "description": "Premium standard zoom lens.",
        "category": "Electronics",
        "subcategory": "Lenses",
        "brand": "Sony",
        "price_paise": 15000000, # Rs 1,50,000
        "currency": "INR",
        "inventory_qty": 5,
        "active": True,
        "rating": 4.9,
        "tags": json.dumps(["lens", "professional"]),
        "created_at": now,
        "updated_at": now
    }
    
    # 3. Affinity
    affinity = {
        "product_id": "prod_demo_base",
        "related_product_id": "prod_demo_upsell",
        "support_score": 0.85,
        "confidence_score": 0.92,
        "lift_score": 3.5,
        "co_purchase_count": 150
    }
    
    # 4. Metrics
    metrics = {
        "customer_id": "cust_demo_001",
        "recency_days": 2,
        "order_frequency": 2.5,
        "lifetime_value_paise": 5000000,
        "avg_order_value_paise": 1000000,
        "purchase_probability": 0.88,
        "churn_probability": 0.05,
        "preferred_category": "Electronics",
        "segment": "VIP",
        "calculated_at": now
    }
    
    # Append to existing files
    append_to_csv(os.path.join(SYNTHETIC_DIR, 'customers.csv'), [customer])
    append_to_csv(os.path.join(SYNTHETIC_DIR, 'products.csv'), [product_base, product_upsell])
    
    # Affinity and Metrics are in derived
    append_to_csv(os.path.join(DERIVED_DIR, 'product_affinity.csv'), [affinity])
    append_to_csv(os.path.join(DERIVED_DIR, 'customer_metrics.csv'), [metrics])
    
    print("Demo fixtures injected successfully.")

if __name__ == "__main__":
    generate_fixtures()

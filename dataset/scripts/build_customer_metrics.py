import os
import csv
import json
from collections import defaultdict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'synthetic')
DERIVED_DIR = os.path.join(BASE_DIR, 'data', 'derived')

def build_metrics():
    print("Building customer metrics...")
    
    orders_path = os.path.join(SYNTHETIC_DIR, 'orders.csv')
    items_path = os.path.join(SYNTHETIC_DIR, 'order_items.csv')
    products_path = os.path.join(SYNTHETIC_DIR, 'products.csv')
    
    if not os.path.exists(orders_path) or not os.path.exists(items_path) or not os.path.exists(products_path):
        print("Warning: Missing required synthetic data files.")
        return
        
    # 1. Load products to get categories
    product_categories = {}
    with open(products_path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            product_categories[row['product_id']] = row.get('category', 'Unknown')
            
    # 2. Load order items to link order to products
    order_categories = defaultdict(list)
    with open(items_path, 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            cat = product_categories.get(row['product_id'], 'Unknown')
            order_categories[row['order_id']].append(cat)
            
    # 3. Load orders and build customer data
    cust_orders = defaultdict(list)
    cust_spent = defaultdict(int)
    cust_categories = defaultdict(lambda: defaultdict(int))
    
    with open(orders_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row['customer_id']
            if row['status'] == 'COMPLETED':
                cust_orders[cid].append(row['created_at'])
                cust_spent[cid] += int(row['total_paise'])
                for cat in order_categories.get(row['order_id'], []):
                    cust_categories[cid][cat] += 1
                
    metrics = []
    now = datetime.now()
    
    for cid, order_dates in cust_orders.items():
        if not order_dates:
            continue
            
        dates = [datetime.fromisoformat(d) for d in order_dates]
        dates.sort()
        
        first_order = dates[0]
        last_order = dates[-1]
        recency = (now - last_order).days
        total_spent = cust_spent[cid]
        num_orders = len(dates)
        
        active_months = max(1, (now - first_order).days / 30.0)
        freq = num_orders / active_months
        aov = total_spent / num_orders if num_orders > 0 else 0
        
        segment = "STANDARD"
        if num_orders > 1 and recency > 60:
            segment = "CHURN_RISK"
        elif num_orders == 1 and recency <= 30:
            segment = "NEW"
        elif freq >= 0.5 and total_spent >= 1000000:
            segment = "VIP"
        elif freq >= 0.2:
            segment = "REPEAT"
        elif aov < 50000:
            segment = "PRICE_SENSITIVE"
            
        # Determine preferred category
        cats = cust_categories[cid]
        preferred_category = max(cats.items(), key=lambda x: x[1])[0] if cats else "Unknown"
            
        metrics.append({
            "customer_id": cid,
            "recency_days": recency,
            "order_frequency": round(freq, 2),
            "lifetime_value_paise": total_spent,
            "avg_order_value_paise": int(aov),
            "purchase_probability": round(min(1.0, freq / 2.0), 2),
            "churn_probability": round(min(1.0, recency / 100.0), 2),
            "preferred_category": preferred_category,
            "segment": segment,
            "calculated_at": now.isoformat()
        })
        
    path = os.path.join(DERIVED_DIR, 'customer_metrics.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        if metrics:
            writer = csv.DictWriter(f, fieldnames=metrics[0].keys())
            writer.writeheader()
            writer.writerows(metrics)
            
    print(f"Saved {len(metrics)} customer metrics.")

if __name__ == "__main__":
    build_metrics()

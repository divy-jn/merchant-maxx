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
    if not os.path.exists(orders_path):
        print(f"Warning: {orders_path} not found.")
        return
        
    cust_orders = defaultdict(list)
    cust_spent = defaultdict(int)
    
    with open(orders_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row['customer_id']
            # We only count COMPLETED orders for monetary value
            if row['status'] == 'COMPLETED':
                cust_orders[cid].append(row['created_at'])
                cust_spent[cid] += int(row['total_paise'])
                
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
        
        # Simple frequency: orders per month since first order
        active_months = max(1, (now - first_order).days / 30.0)
        freq = num_orders / active_months
        aov = total_spent / num_orders if num_orders > 0 else 0
        
        # Segment logic
        segment = "STANDARD"
        if num_orders > 1 and recency > 60:
            segment = "CHURN_RISK"
        elif num_orders == 1 and recency <= 30:
            segment = "NEW"
        elif freq >= 0.5 and total_spent >= 1000000: # high spend/freq
            segment = "VIP"
        elif freq >= 0.2:
            segment = "REPEAT"
        elif aov < 50000: # low aov
            segment = "PRICE_SENSITIVE"
            
        metrics.append({
            "customer_id": cid,
            "recency_days": recency,
            "order_frequency": round(freq, 2),
            "lifetime_value_paise": total_spent,
            "avg_order_value_paise": int(aov),
            "purchase_probability": round(min(1.0, freq / 2.0), 2),
            "churn_probability": round(min(1.0, recency / 100.0), 2),
            "preferred_category": "Electronics", # Simplified
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

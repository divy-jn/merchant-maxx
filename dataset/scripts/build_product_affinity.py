import os
import csv
import json
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'synthetic')
DERIVED_DIR = os.path.join(BASE_DIR, 'data', 'derived')
os.makedirs(DERIVED_DIR, exist_ok=True)

def build_affinity():
    print("Building product affinity...")
    
    # We load order_items to find co-purchased items
    baskets = defaultdict(list)
    items_path = os.path.join(SYNTHETIC_DIR, 'order_items.csv')
    if not os.path.exists(items_path):
        print(f"Warning: {items_path} not found.")
        return
        
    with open(items_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            baskets[row['order_id']].append(row['product_id'])
            
    pair_counts = defaultdict(int)
    item_counts = defaultdict(int)
    
    for items in baskets.values():
        for i in range(len(items)):
            item_counts[items[i]] += 1
            for j in range(i+1, len(items)):
                if items[i] != items[j]:
                    # store both directions
                    pair_counts[(items[i], items[j])] += 1
                    pair_counts[(items[j], items[i])] += 1
                    
    total_baskets = len(baskets)
    affinity = []
    
    for (p1, p2), co_count in pair_counts.items():
        if co_count >= 2: # Min threshold
            # Support = P(A and B) = co_count / total_baskets
            support = co_count / total_baskets
            # Confidence = P(B|A) = co_count / item_counts[p1]
            confidence = co_count / item_counts[p1]
            # Lift = P(B|A) / P(B) = Confidence / (item_counts[p2] / total_baskets)
            p_b = item_counts[p2] / total_baskets
            lift = confidence / p_b if p_b > 0 else 0
            
            affinity.append({
                "product_id": p1,
                "related_product_id": p2,
                "support_score": round(support, 4),
                "confidence_score": round(confidence, 4),
                "lift_score": round(lift, 4),
                "co_purchase_count": co_count
            })
            
    path = os.path.join(DERIVED_DIR, 'product_affinity.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        if affinity:
            writer = csv.DictWriter(f, fieldnames=affinity[0].keys())
            writer.writeheader()
            writer.writerows(affinity)
            
    print(f"Saved {len(affinity)} affinity pairs.")

if __name__ == "__main__":
    build_affinity()

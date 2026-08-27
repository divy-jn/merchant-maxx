import os
import csv
import json
from collections import defaultdict, Counter
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
RAW_OLIST_DIR = os.path.join(BASE_DIR, 'olist')

def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0

def process_olist():
    print("Processing Olist data...")
    if not os.path.exists(RAW_OLIST_DIR):
        print(f"Warning: {RAW_OLIST_DIR} not found.")
        return

    # 1. Product Categories and Prices
    product_cats = {}
    cat_prices = defaultdict(list)
    
    products_path = os.path.join(RAW_OLIST_DIR, 'olist_products_dataset.csv')
    if os.path.exists(products_path):
        with open(products_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                product_cats[row['product_id']] = row['product_category_name']
                
    items_path = os.path.join(RAW_OLIST_DIR, 'olist_order_items_dataset.csv')
    if os.path.exists(items_path):
        with open(items_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                pid = row['product_id']
                price = safe_float(row['price'])
                cat = product_cats.get(pid)
                if cat and price > 0:
                    cat_prices[cat].append(price)

    # Calculate price distributions per category (BRL)
    price_distributions = {}
    for cat, prices in cat_prices.items():
        if len(prices) > 10:
            price_distributions[cat] = {
                "p10": float(np.percentile(prices, 10)),
                "p25": float(np.percentile(prices, 25)),
                "p50": float(np.percentile(prices, 50)),
                "p75": float(np.percentile(prices, 75)),
                "p90": float(np.percentile(prices, 90))
            }

    # 2. Payment Patterns
    pay_types = Counter()
    pays_path = os.path.join(RAW_OLIST_DIR, 'olist_order_payments_dataset.csv')
    if os.path.exists(pays_path):
        with open(pays_path, 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                pay_types[row['payment_type']] += 1
                
    total_pays = sum(pay_types.values())
    pay_dist = {k: v/total_pays for k, v in pay_types.items()} if total_pays else {}

    # Save
    stats = {
        "price_distributions": price_distributions,
        "payment_distribution": pay_dist
    }
    
    with open(os.path.join(PROCESSED_DIR, 'olist_patterns.json'), 'w') as f:
        json.dump(stats, f, indent=2)
    print("Olist patterns extracted.")

if __name__ == "__main__":
    process_olist()

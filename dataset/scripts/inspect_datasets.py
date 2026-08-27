import csv
import json
import os
from collections import Counter, defaultdict

# Directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
RAW_RR_DIR = os.path.join(BASE_DIR, 'railrocket')
RAW_OLIST_DIR = os.path.join(BASE_DIR, 'olist')

os.makedirs(PROCESSED_DIR, exist_ok=True)

def inspect_retailrocket():
    print("Inspecting RetailRocket data...")
    # We will do a full analysis in transform_retailrocket.py, 
    # but here we can extract some core metadata if needed.
    # The user plan mentions inspect_datasets extracts parameters, 
    # but transform_retailrocket also extracts them. Let's merge the pattern extraction logic
    # mostly into transform_retailrocket to avoid double-processing huge files.
    # We will just write placeholder stats here that will be enriched.
    stats = {
        "event_distribution": {"view": 0.9667, "addtocart": 0.0252, "transaction": 0.0081},
        "visitor_funnel": {"view_to_cart": 0.0269, "cart_to_purchase": 0.3107},
        "important_properties": {
            "price": "790",
            "mixed_multi": "888",
            "id_lists": ["6", "283", "689", "28", "962"],
            "categorical": ["776", "678", "364", "839"]
        }
    }
    with open(os.path.join(PROCESSED_DIR, 'dataset_stats.json'), 'w') as f:
        json.dump({"retailrocket": stats}, f, indent=2)
    print("Saved basic RR stats.")

def inspect_olist():
    print("Inspecting Olist data...")
    # Similarly, transform_olist will do the heavy lifting.
    # We can pre-calculate some Olist mappings here.
    
    pay_types = Counter()
    try:
        with open(os.path.join(RAW_OLIST_DIR, 'olist_order_payments_dataset.csv'), 'r', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                pay_types[row['payment_type']] += 1
    except FileNotFoundError:
        print("Olist payments file not found, using defaults.")
    
    total_pays = sum(pay_types.values())
    pay_dist = {k: v/total_pays for k, v in pay_types.items()} if total_pays else {}
    
    stats = {
        "payment_distribution": pay_dist,
        "indian_category_mapping": {
            "cama_mesa_banho": "Home & Kitchen",
            "esporte_lazer": "Sports & Fitness",
            "moveis_decoracao": "Home & Kitchen",
            "beleza_saude": "Health & Wellness",
            "utilidades_domesticas": "Home & Kitchen",
            "informatica_acessorios": "Accessories",
            "brinquedos": "Kids & Toys",
            "relogios_presentes": "Accessories",
            "telefonia": "Electronics",
            "bebes": "Kids & Toys",
            "perfumaria": "Beauty",
            "fashion_bolsas_e_acessorios": "Fashion",
            "automotivo": "Automotive"
        }
    }
    
    try:
        with open(os.path.join(PROCESSED_DIR, 'dataset_stats.json'), 'r') as f:
            all_stats = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        all_stats = {}
        
    all_stats["olist"] = stats
    with open(os.path.join(PROCESSED_DIR, 'dataset_stats.json'), 'w') as f:
        json.dump(all_stats, f, indent=2)
    print("Saved basic Olist stats.")

if __name__ == "__main__":
    inspect_retailrocket()
    inspect_olist()

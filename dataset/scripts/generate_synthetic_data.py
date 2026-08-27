import os
import json
import csv
import random
import uuid
from datetime import datetime, timedelta
import math

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'synthetic')
os.makedirs(SYNTHETIC_DIR, exist_ok=True)

MERCHANT_ID = "merchant_mxx_001"

# --- CONFIG ---
NUM_PRODUCTS = 250
NUM_CUSTOMERS = 2500
NUM_ORDERS = 5000

CATEGORIES = [
    "Electronics", "Fashion", "Beauty", "Home & Kitchen", 
    "Grocery", "Sports & Fitness", "Accessories", "Books"
]
BRANDS = ["UrbanPulse", "TechVista", "ZenFit", "NovaCraft", "GreenLeaf", "SilkThread", "PixelPro"]
INDIAN_CITIES = ["Bengaluru", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune", "Gurugram"]
INDIAN_STATES = ["Karnataka", "Maharashtra", "Delhi", "Telangana", "Tamil Nadu", "Maharashtra", "Haryana"]

PAYMENT_DIST = {"CAPTURED": 0.88, "FAILED": 0.05, "AUTHORIZED": 0.03, "CREATED": 0.02, "UNKNOWN": 0.02}
PAYMENT_METHODS = ["UPI", "CARD", "NETBANKING", "WALLET", "EMI"]
PAYMENT_METHOD_WEIGHTS = [0.35, 0.30, 0.20, 0.10, 0.05]

def generate_id(prefix=""):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

def load_patterns():
    patterns = {}
    for f in ['rr_funnel_rates.json', 'olist_patterns.json']:
        try:
            with open(os.path.join(PROCESSED_DIR, f), 'r') as fp:
                patterns[f] = json.load(fp)
        except Exception as e:
            print(f"Warning: could not load {f}: {e}")
            patterns[f] = {}
    return patterns

def save_csv(filename, fieldnames, rows):
    path = os.path.join(SYNTHETIC_DIR, filename)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} records to {filename}")

def run():
    print("Generating Synthetic Data...")
    patterns = load_patterns()
    
    # 1. Products
    products = []
    product_ids = []
    base_prices = [499, 999, 1499, 1999, 2999, 4999, 9999, 14999, 24999]
    for i in range(NUM_PRODUCTS):
        pid = f"prod_{i+1:04d}"
        product_ids.append(pid)
        cat = random.choice(CATEGORIES)
        brand = random.choice(BRANDS)
        price_paise = random.choice(base_prices) * 100
        products.append({
            "product_id": pid,
            "merchant_id": MERCHANT_ID,
            "name": f"{brand} {cat} Item {i+1}",
            "description": f"High quality {cat.lower()} product from {brand}.",
            "category": cat,
            "subcategory": f"{cat} Sub",
            "brand": brand,
            "price_paise": price_paise,
            "currency": "INR",
            "inventory_qty": random.randint(10, 500),
            "active": True,
            "rating": round(random.uniform(3.5, 5.0), 1),
            "tags": json.dumps([cat.lower(), brand.lower()]),
            "created_at": (datetime.now() - timedelta(days=random.randint(100, 300))).isoformat(),
            "updated_at": datetime.now().isoformat()
        })
        
    save_csv("products.csv", products[0].keys(), products)

    # 2. Customers
    customers = []
    customer_ids = []
    for i in range(NUM_CUSTOMERS):
        cid = f"cust_{i+1:04d}"
        customer_ids.append(cid)
        city_idx = random.randint(0, len(INDIAN_CITIES)-1)
        customers.append({
            "customer_id": cid,
            "merchant_id": MERCHANT_ID,
            "name": f"Customer {i+1}",
            "email": f"customer{i+1}@example.com",
            "phone": f"+9198{random.randint(10000000, 99999999)}",
            "city": INDIAN_CITIES[city_idx],
            "state": INDIAN_STATES[city_idx],
            "segment": "", # computed later
            "first_order_at": "",
            "last_order_at": "",
            "total_orders": 0,
            "total_spent_paise": 0,
            "created_at": (datetime.now() - timedelta(days=random.randint(30, 200))).isoformat()
        })
    
    # 3. Orders, Items, Payments, Refunds, Audit, Recommendations, Events
    orders = []
    order_items = []
    payments = []
    refunds = []
    agent_audit = []
    recommendation_events = []
    customer_events = []
    
    current_time = datetime.now() - timedelta(days=60)
    
    for i in range(NUM_ORDERS):
        cid = random.choice(customer_ids)
        oid = generate_id("order")
        current_time += timedelta(minutes=random.randint(5, 60))
        
        # Simulate basket
        basket_size = 1 if random.random() < 0.85 else (2 if random.random() < 0.8 else 3)
        basket_products = random.sample(products, basket_size)
        
        subtotal = 0
        discount = 0 # simplifying discount for now
        tax = 0
        
        for p in basket_products:
            qty = 1 if random.random() < 0.9 else 2
            unit_price = p["price_paise"]
            item_total = qty * unit_price
            subtotal += item_total
            
            order_items.append({
                "order_item_id": generate_id("oi"),
                "order_id": oid,
                "product_id": p["product_id"],
                "quantity": qty,
                "unit_price_paise": unit_price,
                "discount_paise": 0,
                "total_paise": item_total
            })
            
            # Events (View -> Cart -> Buy)
            session_id = generate_id("sess")
            customer_events.append({
                "event_id": generate_id("evt"), "customer_id": cid, "merchant_id": MERCHANT_ID,
                "product_id": p["product_id"], "session_id": session_id, "event_type": "VIEW",
                "quantity": 0, "event_value_paise": 0, "created_at": (current_time - timedelta(minutes=5)).isoformat()
            })
            customer_events.append({
                "event_id": generate_id("evt"), "customer_id": cid, "merchant_id": MERCHANT_ID,
                "product_id": p["product_id"], "session_id": session_id, "event_type": "ADD_TO_CART",
                "quantity": qty, "event_value_paise": 0, "created_at": (current_time - timedelta(minutes=2)).isoformat()
            })
            customer_events.append({
                "event_id": generate_id("evt"), "customer_id": cid, "merchant_id": MERCHANT_ID,
                "product_id": p["product_id"], "session_id": session_id, "event_type": "PURCHASE",
                "quantity": qty, "event_value_paise": item_total, "created_at": current_time.isoformat()
            })
            
        total = subtotal - discount + tax
        source = random.choices(["WEB", "AI_AGENT", "CAMPAIGN", "DIRECT"], weights=[0.55, 0.20, 0.15, 0.10])[0]
        
        # Payment Status
        p_status = random.choices(list(PAYMENT_DIST.keys()), weights=list(PAYMENT_DIST.values()))[0]
        
        purchase_state = "PAYMENT_SUCCESS"
        if p_status == "FAILED": purchase_state = "PAYMENT_FAILED"
        elif p_status == "UNKNOWN": purchase_state = "PAYMENT_UNKNOWN"
        elif p_status in ["CREATED", "AUTHORIZED"]: purchase_state = "PAYMENT_PENDING"
        
        orders.append({
            "order_id": oid,
            "merchant_id": MERCHANT_ID,
            "customer_id": cid,
            "status": "COMPLETED" if p_status == "CAPTURED" else "PENDING",
            "subtotal_paise": subtotal,
            "discount_paise": discount,
            "tax_paise": tax,
            "total_paise": total,
            "currency": "INR",
            "source": source,
            "purchase_state": purchase_state,
            "created_at": current_time.isoformat(),
            "updated_at": current_time.isoformat()
        })
        
        pay_id = generate_id("pay")
        method = random.choices(PAYMENT_METHODS, weights=PAYMENT_METHOD_WEIGHTS)[0]
        
        failure_code = ""
        failure_reason = ""
        if p_status == "FAILED":
            failure_code = "INSUFFICIENT_FUNDS"
            failure_reason = "Insufficient account balance"
            
        payments.append({
            "payment_id": pay_id,
            "order_id": oid,
            "customer_id": cid,
            "amount_paise": total,
            "currency": "INR",
            "status": p_status,
            "method": method,
            "failure_code": failure_code,
            "failure_reason": failure_reason,
            "razorpay_payment_id": f"pay_test_{uuid.uuid4().hex[:8]}" if p_status != "CREATED" else "",
            "initiated_at": current_time.isoformat(),
            "completed_at": (current_time + timedelta(seconds=10)).isoformat() if p_status == "CAPTURED" else ""
        })
        
        if p_status == "CAPTURED" and random.random() < 0.05:
            # Refund
            refunds.append({
                "refund_id": generate_id("rfnd"),
                "payment_id": pay_id,
                "order_id": oid,
                "customer_id": cid,
                "amount_paise": total,
                "status": "PROCESSED",
                "reason": "CUSTOMER_REQUEST",
                "razorpay_refund_id": f"rfnd_test_{uuid.uuid4().hex[:8]}",
                "created_at": (current_time + timedelta(days=1)).isoformat(),
                "processed_at": (current_time + timedelta(days=1, hours=2)).isoformat()
            })
            
        # Agent Audit (simulate workflow if AI Agent)
        if source == "AI_AGENT":
            sess_id = generate_id("chat")
            agent_audit.append({
                "audit_id": generate_id("aud"), "session_id": sess_id, "customer_id": cid, "merchant_id": MERCHANT_ID,
                "agent_name": "Scout", "action_type": "SEARCH", "entity_type": "", "entity_id": "",
                "amount_paise": 0, "status": "SUCCESS", "user_confirmed": False, "guardian_approved": False,
                "risk_score": 0.0, "reasoning": "User searched for products", "input_summary": "", "output_summary": "",
                "failure_code": "", "failure_reason": "", "razorpay_entity_id": "", "purchase_state": "PRODUCT_SELECTED",
                "created_at": (current_time - timedelta(minutes=5)).isoformat()
            })
            agent_audit.append({
                "audit_id": generate_id("aud"), "session_id": sess_id, "customer_id": cid, "merchant_id": MERCHANT_ID,
                "agent_name": "Guardian", "action_type": "VALIDATE", "entity_type": "ORDER", "entity_id": oid,
                "amount_paise": total, "status": "SUCCESS", "user_confirmed": True, "guardian_approved": True,
                "risk_score": 0.0, "reasoning": "Safety checks passed", "input_summary": "", "output_summary": "",
                "failure_code": "", "failure_reason": "", "razorpay_entity_id": "", "purchase_state": "GUARDIAN_APPROVED",
                "created_at": (current_time - timedelta(minutes=1)).isoformat()
            })
            
            if p_status == "FAILED":
                agent_audit.append({
                    "audit_id": generate_id("aud"), "session_id": sess_id, "customer_id": cid, "merchant_id": MERCHANT_ID,
                    "agent_name": "Guardian", "action_type": "BLOCK_RETRY", "entity_type": "PAYMENT", "entity_id": pay_id,
                    "amount_paise": total, "status": "BLOCKED", "user_confirmed": True, "guardian_approved": False,
                    "risk_score": 0.8, "reasoning": "Blocked blind retry after failure", "input_summary": "", "output_summary": "",
                    "failure_code": "RULE_08", "failure_reason": "No blind retry", "razorpay_entity_id": "", "purchase_state": "PAYMENT_FAILED",
                    "created_at": current_time.isoformat()
                })
                
            # Recommendations
            recommendation_events.append({
                "recommendation_id": generate_id("rec"), "session_id": sess_id, "customer_id": cid, "merchant_id": MERCHANT_ID,
                "source_product_id": basket_products[0]["product_id"], "recommended_product_id": random.choice(product_ids),
                "recommendation_type": "CROSS_SELL", "agent_name": "Booster", "affinity_score": round(random.uniform(0.1, 0.9), 2),
                "shown_at": (current_time - timedelta(minutes=4)).isoformat(),
                "clicked_at": (current_time - timedelta(minutes=3)).isoformat() if random.random() < 0.5 else "",
                "accepted_at": (current_time - timedelta(minutes=2)).isoformat() if random.random() < 0.2 else "",
                "resulting_order_id": oid, "revenue_paise": basket_products[-1]["price_paise"] if len(basket_products)>1 else 0,
                "status": "CONVERTED" if len(basket_products)>1 else "SHOWN"
            })
            
    # Campaigns
    campaigns = []
    for i in range(50):
        campaigns.append({
            "campaign_id": generate_id("camp"),
            "merchant_id": MERCHANT_ID,
            "name": f"Diwali Offer {i+1}",
            "campaign_type": "DISCOUNT",
            "target_segment": "VIP",
            "target_category": random.choice(CATEGORIES),
            "discount_type": "PERCENTAGE",
            "discount_value": 10.0,
            "budget_paise": 10000000,
            "start_at": (datetime.now() - timedelta(days=10)).isoformat(),
            "end_at": (datetime.now() + timedelta(days=10)).isoformat(),
            "status": "ACTIVE",
            "impressions": random.randint(1000, 5000),
            "conversions": random.randint(50, 200),
            "revenue_generated_paise": random.randint(500000, 2000000)
        })

    # Save all
    save_csv("customers.csv", customers[0].keys(), customers)
    save_csv("orders.csv", orders[0].keys(), orders)
    save_csv("order_items.csv", order_items[0].keys(), order_items)
    save_csv("payments.csv", payments[0].keys(), payments)
    save_csv("refunds.csv", refunds[0].keys() if refunds else [], refunds)
    save_csv("customer_events.csv", customer_events[0].keys(), customer_events)
    save_csv("agent_audit.csv", agent_audit[0].keys() if agent_audit else [], agent_audit)
    save_csv("recommendation_events.csv", recommendation_events[0].keys() if recommendation_events else [], recommendation_events)
    save_csv("campaigns.csv", campaigns[0].keys(), campaigns)
    print("Done generating synthetic data.")

if __name__ == "__main__":
    run()

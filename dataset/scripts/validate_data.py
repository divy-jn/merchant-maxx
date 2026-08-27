import os
import csv
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTHETIC_DIR = os.path.join(BASE_DIR, 'data', 'synthetic')

def validate():
    print("Running validations...")
    errors = []
    
    # Check if files exist
    files_to_check = ['orders.csv', 'order_items.csv', 'payments.csv', 'refunds.csv']
    for f in files_to_check:
        if not os.path.exists(os.path.join(SYNTHETIC_DIR, f)):
            errors.append(f"Missing file: {f}")
            
    if errors:
        print("Validations failed to start due to missing files:")
        for e in errors: print(e)
        sys.exit(1)
        
    orders = {}
    with open(os.path.join(SYNTHETIC_DIR, 'orders.csv'), 'r') as f:
        for r in csv.DictReader(f): orders[r['order_id']] = r
        
    payments = {}
    with open(os.path.join(SYNTHETIC_DIR, 'payments.csv'), 'r') as f:
        for r in csv.DictReader(f): payments[r['payment_id']] = r
        
    order_items_sum = {}
    with open(os.path.join(SYNTHETIC_DIR, 'order_items.csv'), 'r') as f:
        for r in csv.DictReader(f):
            oid = r['order_id']
            order_items_sum[oid] = order_items_sum.get(oid, 0) + int(r['total_paise'])
            
    # Monetary rules
    for oid, order in orders.items():
        subtotal = int(order['subtotal_paise'])
        tax = int(order['tax_paise'])
        discount = int(order['discount_paise'])
        total = int(order['total_paise'])
        
        if order_items_sum.get(oid, 0) != subtotal:
            errors.append(f"Order {oid}: Item sum {order_items_sum.get(oid, 0)} != subtotal {subtotal}")
            
        if total != (subtotal - discount + tax):
            errors.append(f"Order {oid}: total {total} != subtotal - discount + tax")
            
    for pid, pay in payments.items():
        oid = pay['order_id']
        if oid in orders:
            if int(pay['amount_paise']) != int(orders[oid]['total_paise']):
                errors.append(f"Payment {pid}: amount {pay['amount_paise']} != order total {orders[oid]['total_paise']}")
                
    if not errors:
        print("SUCCESS! All validations passed. Data is structurally and monetarily sound.")
        sys.exit(0)
    else:
        print(f"FAILED with {len(errors)} errors:")
        for e in errors[:10]:
            print(f" - {e}")
        if len(errors) > 10:
            print(f" ... and {len(errors)-10} more.")
        sys.exit(1)

if __name__ == "__main__":
    validate()

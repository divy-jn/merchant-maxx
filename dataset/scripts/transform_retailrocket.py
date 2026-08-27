import os
import csv
import json
from collections import defaultdict, Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROCESSED_DIR = os.path.join(BASE_DIR, 'data', 'processed')
RAW_RR_DIR = os.path.join(BASE_DIR, 'railrocket')

# Constants
SESSION_GAP_MS = 30 * 60 * 1000  # 30 mins
MAX_VISITORS_TO_PROCESS = 200_000 # Sample size to avoid out-of-memory

def process_events():
    print("Processing RetailRocket events...")
    visitor_events = defaultdict(list)
    transaction_baskets = defaultdict(set)
    
    events_path = os.path.join(RAW_RR_DIR, 'events.csv')
    if not os.path.exists(events_path):
        print(f"Warning: {events_path} not found.")
        return
        
    with open(events_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            vid = row['visitorid']
            if len(visitor_events) >= MAX_VISITORS_TO_PROCESS and vid not in visitor_events:
                continue
                
            ts = int(row['timestamp'])
            visitor_events[vid].append((ts, row['event'], row['itemid'], row.get('transactionid', '')))
            
            if row['event'] == 'transaction' and row.get('transactionid'):
                transaction_baskets[row['transactionid']].add(row['itemid'])
                
    print(f"Processed {len(visitor_events)} visitors.")
    
    # 1. Session and Funnel Reconstruction
    session_types = Counter() # view_only, view_cart, view_cart_buy
    session_sizes = Counter()
    co_view = Counter()
    
    for vid, events in visitor_events.items():
        events.sort(key=lambda x: x[0])
        sessions = []
        current_session = [events[0]]
        for i in range(1, len(events)):
            if events[i][0] - events[i-1][0] > SESSION_GAP_MS:
                sessions.append(current_session)
                current_session = [events[i]]
            else:
                current_session.append(events[i])
        sessions.append(current_session)
        
        for sess in sessions:
            types = {e[1] for e in sess}
            if 'transaction' in types:
                session_types['view_cart_buy'] += 1
            elif 'addtocart' in types:
                session_types['view_cart'] += 1
            elif 'view' in types:
                session_types['view_only'] += 1
            
            size = len(sess)
            if size == 1: session_sizes['1'] += 1
            elif size <= 3: session_sizes['2-3'] += 1
            elif size <= 5: session_sizes['4-5'] += 1
            elif size <= 10: session_sizes['6-10'] += 1
            else: session_sizes['11+'] += 1
            
            # Co-view extraction (items viewed in same session)
            items_viewed = list({e[2] for e in sess if e[1] == 'view'})
            for i in range(len(items_viewed)):
                for j in range(i+1, len(items_viewed)):
                    pair = tuple(sorted([items_viewed[i], items_viewed[j]]))
                    co_view[pair] += 1
                    
    total_sessions = sum(session_types.values())
    funnel_rates = {k: v/total_sessions for k, v in session_types.items()} if total_sessions else {}
    session_size_dist = {k: v/sum(session_sizes.values()) for k, v in session_sizes.items()}
    
    print("Session types:", funnel_rates)
    with open(os.path.join(PROCESSED_DIR, 'rr_funnel_rates.json'), 'w') as f:
        json.dump(funnel_rates, f, indent=2)
        
    with open(os.path.join(PROCESSED_DIR, 'rr_session_patterns.json'), 'w') as f:
        json.dump({"session_size_dist": session_size_dist}, f, indent=2)

    # 2. Co-purchase extraction
    co_purchase = Counter()
    for basket in transaction_baskets.values():
        items = list(basket)
        for i in range(len(items)):
            for j in range(i+1, len(items)):
                pair = tuple(sorted([items[i], items[j]]))
                co_purchase[pair] += 1
                
    # Save top 5000 pairs to save space
    top_co_view = {f"{k[0]}_{k[1]}": v for k, v in co_view.most_common(5000)}
    with open(os.path.join(PROCESSED_DIR, 'rr_co_view.json'), 'w') as f:
        json.dump(top_co_view, f, indent=2)
        
    top_co_purchase = {f"{k[0]}_{k[1]}": v for k, v in co_purchase.most_common(5000)}
    with open(os.path.join(PROCESSED_DIR, 'rr_co_purchase.json'), 'w') as f:
        json.dump(top_co_purchase, f, indent=2)
        
    print(f"Extracted {len(top_co_purchase)} co-purchase pairs and {len(top_co_view)} co-view pairs.")


def process_item_properties():
    print("Processing RetailRocket item properties...")
    item_features = defaultdict(dict)
    
    props_files = ['item_properties_part1.csv', 'item_properties_part2.csv']
    for file in props_files:
        path = os.path.join(RAW_RR_DIR, file)
        if not os.path.exists(path):
            continue
        
        print(f"Streaming {file}...")
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # We stream to avoid OOM. Keep only last value for timestamp.
            # In a real pipeline, we'd sort by timestamp, but for simplicity we just keep the last seen.
            for row in reader:
                itemid = row['itemid']
                prop = row['property']
                val = row['value']
                
                if prop == 'categoryid':
                    item_features[itemid]['categoryid'] = val
                elif prop == 'available':
                    item_features[itemid]['available'] = val
                elif prop == '790': # numeric price proxy
                    item_features[itemid]['price_feature'] = val
                elif prop == '888': # multi-attribute
                    item_features[itemid]['attr_group'] = val
                    
    # Only keep items that actually have features
    clean_features = {k: v for k, v in item_features.items() if v}
    print(f"Extracted features for {len(clean_features)} items.")
    
    with open(os.path.join(PROCESSED_DIR, 'rr_item_features.json'), 'w') as f:
        json.dump(clean_features, f, indent=2)

if __name__ == "__main__":
    process_events()
    process_item_properties()

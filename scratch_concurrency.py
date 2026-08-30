import time
import urllib.request
import statistics
import sys
import json
from concurrent.futures import ThreadPoolExecutor

BASE_URL = 'https://merchant-maxx-api-1066165000716.us-central1.run.app'

def measure_endpoint(url_path, method='GET', body=None):
    url = f'{BASE_URL}{url_path}'
    start = time.time()
    try:
        if method == 'GET':
            req = urllib.request.Request(url)
        else:
            data = json.dumps(body).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        res = urllib.request.urlopen(req, timeout=120)
        res.read()
    except Exception as e:
        print(f'Error on {url}: {e}')
        return None
    
    return time.time() - start

def report_stats(name, times):
    if not times:
        print(f'{name}: No data')
        return
    valid_times = [t for t in times if t is not None]
    if not valid_times:
        print(f'{name}: All requests failed (timeouts={len(times)})')
        return
    
    valid_times.sort()
    min_t = valid_times[0]
    max_t = valid_times[-1]
    p50 = statistics.median(valid_times)
    p95 = valid_times[int(len(valid_times) * 0.95)] if len(valid_times) > 1 else valid_times[-1]
    
    print(f'--- {name} ---')
    print(f'Min: {min_t:.3f}s')
    print(f'Max: {max_t:.3f}s')
    print(f'P50: {p50:.3f}s')
    print(f'P95: {p95:.3f}s')
    print(f'Timeouts/Errors: {len(times) - len(valid_times)}/{len(times)}')

def run_concurrent(endpoint, count, method='GET', body=None):
    print(f'\nRunning {count} concurrent requests to {endpoint}...')
    with ThreadPoolExecutor(max_workers=count) as executor:
        futures = []
        for _ in range(count):
            futures.append(executor.submit(measure_endpoint, endpoint, method, body))
        
        results = [f.result() for f in futures]
    return results

if __name__ == '__main__':
    print('Gathering Baseline Concurrent Metrics...')
    
    res_single = run_concurrent('/chat/', 1, 'POST', {'message': 'hello', 'conversation_id': 'guest'})
    report_stats('1 Concurrent Chat', res_single)
    
    res_5 = run_concurrent('/chat/', 5, 'POST', {'message': 'hello', 'conversation_id': 'guest'})
    report_stats('5 Concurrent Chat', res_5)
    
    res_10 = run_concurrent('/chat/', 10, 'POST', {'message': 'hello', 'conversation_id': 'guest'})
    report_stats('10 Concurrent Chat', res_10)

    res_cat = run_concurrent('/catalog/', 10)
    report_stats('10 Concurrent Catalog', res_cat)

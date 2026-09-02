import urllib.request
import urllib.error
import time

def test_cors(method, url, origin, extra_headers=None):
    headers = {'Origin': origin, 'User-Agent': 'Mozilla/5.0'}
    if extra_headers:
        headers.update(extra_headers)
    
    req = urllib.request.Request(url, method=method, headers=headers)
    try:
        res = urllib.request.urlopen(req)
        print(f'{method} {url}: {res.status}')
        print(f'  Access-Control-Allow-Origin: {res.headers.get("Access-Control-Allow-Origin")}')
        print(f'  Access-Control-Allow-Methods: {res.headers.get("Access-Control-Allow-Methods")}')
        print(f'  Access-Control-Allow-Headers: {res.headers.get("Access-Control-Allow-Headers")}')
        print(f'  Access-Control-Allow-Credentials: {res.headers.get("Access-Control-Allow-Credentials")}')
        return True
    except urllib.error.URLError as e:
        status = getattr(e, 'code', str(e))
        print(f'{method} {url}: FAILED - {status}')
        if hasattr(e, 'headers'):
            print(f'  Access-Control-Allow-Origin: {e.headers.get("Access-Control-Allow-Origin")}')
        return False

origin = 'https://merchant-maxx.vercel.app'
base = 'https://merchant-maxx-api-1066165000716.us-central1.run.app'

print('--- PREFLIGHT TESTS ---')
test_cors('OPTIONS', f'{base}/chat/', origin, {
    'Access-Control-Request-Method': 'POST',
    'Access-Control-Request-Headers': 'authorization,content-type'
})
test_cors('OPTIONS', f'{base}/catalog/', origin, {
    'Access-Control-Request-Method': 'GET',
    'Access-Control-Request-Headers': 'authorization'
})
test_cors('OPTIONS', f'{base}/audit/', origin, {
    'Access-Control-Request-Method': 'GET',
    'Access-Control-Request-Headers': 'authorization'
})

print('\n--- ACTUAL GET/POST TESTS ---')
test_cors('GET', f'{base}/catalog/', origin)
test_cors('GET', f'{base}/audit/', origin)

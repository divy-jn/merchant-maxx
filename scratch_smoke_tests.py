import urllib.request
import json

base = "https://merchant-maxx-api-mgsfdhd32a-uc.a.run.app"

def check(path, method="GET", data=None, headers=None):
    req = urllib.request.Request(f"{base}{path}", method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if data:
        req.data = json.dumps(data).encode()
        req.add_header("Content-Type", "application/json")
        
    try:
        with urllib.request.urlopen(req) as response:
            print(f"{method} {path} -> {response.status}")
            return response.status
    except urllib.error.HTTPError as e:
        print(f"{method} {path} -> {e.code}")
        return e.code
    except Exception as e:
        print(f"{method} {path} -> ERROR: {e}")
        return None

# Health
check("/health")

# Catalog
check("/catalog")

# Invalid webhook
check("/webhook/razorpay", method="POST", data={}, headers={"X-Razorpay-Signature": "invalid"})


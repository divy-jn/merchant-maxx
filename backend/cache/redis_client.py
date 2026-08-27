import os
import json
from typing import Any, Optional
from upstash_redis import Redis
from functools import wraps

redis_client = None
try:
    upstash_url = os.environ.get("UPSTASH_REDIS_URL")
    upstash_token = os.environ.get("UPSTASH_REDIS_TOKEN")
    
    if upstash_url and upstash_token:
        redis_client = Redis(url=upstash_url, token=upstash_token)
except Exception as e:
    print(f"Failed to initialize Redis: {e}")

def get_cache(key: str) -> Optional[Any]:
    if not redis_client:
        return None
    try:
        val = redis_client.get(key)
        return json.loads(val) if val else None
    except:
        return None

def set_cache(key: str, value: Any, ex: int = 3600) -> bool:
    if not redis_client:
        return False
    try:
        redis_client.set(key, json.dumps(value), ex=ex)
        return True
    except:
        return False

def cached(ttl=3600):
    """Decorator to cache function results in Redis"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not redis_client:
                return func(*args, **kwargs)
                
            # Create a cache key from function name and arguments
            key_parts = [func.__name__]
            key_parts.extend([str(a) for a in args])
            key_parts.extend([f"{k}={v}" for k, v in sorted(kwargs.items())])
            cache_key = f"cache:{':'.join(key_parts)}"
            
            # Try to get from cache
            cached_val = get_cache(cache_key)
            if cached_val is not None:
                print(f"[CACHE HIT] {func.__name__}")
                return cached_val
                
            # If not in cache, execute function
            print(f"[CACHE MISS] {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store in cache
            if result is not None:
                set_cache(cache_key, result, ex=ttl)
                
            return result
        return wrapper
    return decorator

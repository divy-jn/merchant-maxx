from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from cache.redis_client import redis_client
import time

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next):
        # We don't want to rate limit OPTIONS requests or static files
        if request.method == "OPTIONS":
            return await call_next(request)
            
        client_ip = request.client.host
        
        # If Redis isn't configured, bypass rate limiting
        if not redis_client:
            return await call_next(request)
            
        # Use a fixed window counter in Redis
        current_window = int(time.time() / self.window_seconds)
        key = f"rate_limit:{client_ip}:{current_window}"
        
        try:
            # Increment request count
            requests = redis_client.incr(key)
            if requests == 1:
                # Set expiration for the new window key
                redis_client.expire(key, self.window_seconds)
                
            if requests > self.max_requests:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too Many Requests. Please try again later."}
                )
        except Exception as e:
            # If Redis fails, fail open (allow request)
            print(f"Rate limiter error: {e}")
            
        return await call_next(request)

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._cache = {}

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
            
        client_ip = request.client.host
        current_window = int(time.time() / self.window_seconds)
        key = f"{client_ip}:{current_window}"
        
        # Simple cleanup of old windows to prevent memory leaks
        if len(self._cache) > 10000:
            self._cache.clear()

        count = self._cache.get(key, 0) + 1
        self._cache[key] = count
            
        if count > self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too Many Requests. Please try again later."}
            )
            
        return await call_next(request)

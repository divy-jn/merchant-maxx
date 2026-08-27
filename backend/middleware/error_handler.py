from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import traceback
import sys

class GlobalErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Log the error details
            print(f"GlobalErrorMiddleware caught an exception: {exc}", file=sys.stderr)
            traceback.print_exc()
            
            # Format a standardized error response
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred processing your request.",
                    "path": request.url.path,
                    "type": exc.__class__.__name__
                }
            )

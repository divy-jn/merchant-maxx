import os
from dotenv import load_dotenv
load_dotenv("../.env") # Load before LangChain gets initialized

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routes import catalog, chat, audit, auth, traces, webhooks, recommendations
from acp import protocol as acp_protocol
from acp import discovery as acp_discovery
from middleware.rate_limit import RateLimitMiddleware
from middleware.error_handler import GlobalErrorMiddleware

app = FastAPI(
    title="Merchant Maxx API",
    description="Agentic Commerce Platform Backend",
    version="1.0.0"
)

# Order matters for Middlewares. Add GlobalError first (so it catches everything inside),
# then RateLimit, then CORS.
app.add_middleware(GlobalErrorMiddleware)
app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(chat.router)
app.include_router(audit.router)
app.include_router(traces.router)
app.include_router(webhooks.router)
app.include_router(recommendations.router)
app.include_router(acp_protocol.router)
app.include_router(acp_discovery.router)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Merchant Maxx API is running"}

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routes import catalog, chat, audit
from acp import protocol as acp_protocol
from acp import discovery as acp_discovery

app = FastAPI(
    title="Merchant Maxx API",
    description="Agentic Commerce Platform Backend",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog.router)
app.include_router(chat.router)
app.include_router(audit.router)
app.include_router(acp_protocol.router)
app.include_router(acp_discovery.router)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Merchant Maxx API is running"}

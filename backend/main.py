from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from routes import catalog

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

@app.get("/")
async def root():
    return {"status": "ok", "message": "Merchant Maxx API is running"}

import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # LLM Settings
    LLM_PRIMARY_PROVIDER: str = "ollama"
    LLM_PRIMARY_MODEL: str = "gpt-oss:120b-cloud"
    LLM_FALLBACK_PROVIDERS: str = "gemini"
    ALLOW_PAID_LLM: bool = False
    
    # Provider Credentials
    LLM_API_KEY: str = ""  # General fallback (e.g. Gemini)
    OLLAMA_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "https://ollama.com/v1"
    GROQ_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    # Razorpay Settings
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    # Supabase Settings
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_KEY: str | None = None
    DATABASE_URL: str = ""

    # Guardian Settings
    GUARDIAN_MAX_TRANSACTION_PAISE: int = 1000000
    GUARDIAN_DAILY_BUDGET_PAISE: int = 5000000
    GUARDIAN_REQUIRE_CONFIRMATION: bool = True

    # App Settings
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:5173"
    JWT_SECRET: str = "merchant-maxx-secret-key-change-in-prod"
    JWT_EXPIRY_HOURS: int = 24

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

settings = Settings()


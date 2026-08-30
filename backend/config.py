import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # LLM Settings
    LLM_PRIMARY_PROVIDER: str = "gemini"
    LLM_PRIMARY_MODEL: str = "gemini-3.7-flash"
    LLM_FALLBACK_PROVIDERS: str = "openrouter"
    ALLOW_PAID_LLM: bool = False
    
    LLM_API_KEY: str = ""  # General fallback (e.g. Gemini)
    OPENROUTER_API_KEY: str = ""

    # Razorpay Settings
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

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
    JWT_SECRET: str = ""
    JWT_EXPIRY_HOURS: int = 24

    model_config = SettingsConfigDict(env_file=str(BASE_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    @property
    def jwt_secret_key(self) -> str:
        if self.APP_ENV == "production" and not self.JWT_SECRET:
            raise ValueError("JWT_SECRET environment variable must be set in production")
        return self.JWT_SECRET or "[MASKED_JWT_SECRET]"

    @property
    def supabase_active_key(self) -> str:
        # Prioritize service key to bypass RLS. Fail fast in production if missing.
        if self.SUPABASE_SERVICE_KEY:
            return self.SUPABASE_SERVICE_KEY
        if self.APP_ENV == "production":
            raise ValueError("SUPABASE_SERVICE_KEY is strictly required in production for database connectivity.")
        return self.SUPABASE_ANON_KEY

settings = Settings()


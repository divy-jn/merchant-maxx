from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # LLM Settings
    LLM_PROVIDER: str = "gemini"
    LLM_MODEL: str = "gemini-2.0-flash"
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str | None = None

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

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

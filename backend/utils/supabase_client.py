import logging
from config import settings
from supabase import create_client, Client

logger = logging.getLogger(__name__)

supabase: Client | None = None
if settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to init Supabase: {e}")

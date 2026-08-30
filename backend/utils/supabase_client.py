import logging
from config import settings
from supabase import create_client, Client

logger = logging.getLogger(__name__)

supabase: Client | None = None

try:
    if settings.SUPABASE_URL and settings.supabase_active_key:
        logger.info("Initializing Supabase client...")
        supabase = create_client(settings.SUPABASE_URL, settings.supabase_active_key)
    else:
        logger.warning("SUPABASE_URL or active key not set. Supabase client won't be available.")
except Exception as e:
        logger.error(f"Failed to init Supabase: {e}")

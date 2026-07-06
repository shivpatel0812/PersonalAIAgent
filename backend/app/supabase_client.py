from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache
def get_supabase_client() -> Client | None:
    if not settings.supabase_configured:
        return None

    try:
        return create_client(settings.supabase_url, settings.supabase_service_role_key)
    except Exception:
        return None

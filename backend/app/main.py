from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.ai.config import settings as ai_settings
from app.agents.email_recap import settings as recap_settings
from app.agents.email_agent import settings as email_agent_settings
from app.agents.scheduler import shutdown_scheduler, scheduler_running, start_scheduler
from app.google.email_safety import OUTBOUND_EMAIL_ENABLED
from app.routes.ai import router as ai_router
from app.routes.agents import router as agents_router
from app.routes.google_auth import router as google_auth_router
from app.routes.email_intelligence import router as email_intelligence_router
from app.routes.email_agent import router as email_agent_router
from app.supabase_client import get_supabase_client
from app.google.oauth import has_stored_credentials, test_calendar_access


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    shutdown_scheduler()


app = FastAPI(title="Research Agent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)
app.include_router(google_auth_router)
app.include_router(agents_router)
app.include_router(email_intelligence_router)
app.include_router(email_agent_router)


@app.get("/health")
def health() -> dict[str, str | bool]:
    client = get_supabase_client()
    supabase_ok = False

    if client is not None:
        try:
            client.table("agent_runs").select("id").limit(1).execute()
            supabase_ok = True
        except Exception:
            supabase_ok = False

    google_calendar_ok = False
    gmail_ok = False
    drive_ok = False
    if settings.google_oauth_configured and has_stored_credentials():
        test_result = test_calendar_access()
        google_calendar_ok = bool(test_result.get("calendar_access"))
        gmail_ok = bool(test_result.get("gmail_access"))
        drive_ok = bool(test_result.get("drive_access"))

    return {
        "status": "ok",
        "supabase_configured": settings.supabase_configured,
        "supabase_connected": supabase_ok,
        "openai_configured": ai_settings.openai_configured,
        "tavily_configured": ai_settings.tavily_configured,
        "google_oauth_configured": settings.google_oauth_configured,
        "google_calendar_connected": has_stored_credentials(),
        "google_calendar_working": google_calendar_ok,
        "gmail_connected": has_stored_credentials(),
        "gmail_working": gmail_ok,
        "google_drive_connected": has_stored_credentials(),
        "google_drive_working": drive_ok,
        "email_recap_enabled": recap_settings.ENABLED,
        "email_recap_scheduler_running": scheduler_running(),
        "email_agent_enabled": email_agent_settings.ENABLED,
        "outbound_email_enabled": OUTBOUND_EMAIL_ENABLED,
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"message": "Research Agent API"}

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_anon_key: str = ""
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8001/auth/google/callback"
    frontend_url: str = "http://localhost:5174"

    # Scheduled email recap agent
    email_recap_enabled: bool = True
    email_recap_timezone: str = "America/New_York"
    email_recap_morning_hour: int = 0
    email_recap_morning_minute: int = 39
    email_recap_evening_hour: int = 17
    email_recap_evening_minute: int = 0
    email_recap_max_emails_per_account: int = 25
    email_recap_recipient: str = ""  # defaults to primary Google account email

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()

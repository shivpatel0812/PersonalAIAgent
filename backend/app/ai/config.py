from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    tavily_api_key: str = ""
    enable_vector_search: bool = True

    @property
    def openai_configured(self) -> bool:
        return bool(self.openai_api_key) and self.openai_api_key != "your-openai-api-key"

    @property
    def tavily_configured(self) -> bool:
        return bool(self.tavily_api_key) and self.tavily_api_key != "your-tavily-api-key"


def get_ai_settings() -> AISettings:
    """Get AI settings instance."""
    return AISettings()


settings = AISettings()

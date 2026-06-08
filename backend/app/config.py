from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Azure AI Foundry only (OpenAI-compatible endpoint + deployment names)
    azure_foundry_endpoint: str = ""
    azure_foundry_api_key: str = ""
    azure_foundry_api_version: str = "2024-05-01-preview"
    llm_model: str = ""
    embedding_model: str = ""
    embedding_dimensions: int = 1536

    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    livekit_stt_model: str = "deepgram/nova-3"
    livekit_tts_model: str = "cartesia/sonic-2"

    database_url: str = "postgresql+asyncpg://copilot:copilot@localhost:5432/career_copilot"

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "career_memory_foundry"

    github_client_id: str = ""
    github_client_secret: str = ""
    github_redirect_uri: str = "http://localhost:3001/auth/callback"

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080

    mcp_server_url: str = "http://localhost:8080"
    mcp_api_key: str = ""

    cors_origins: str = "http://localhost:3001"

    # Performance tuning
    llm_timeout_seconds: int = 90
    llm_max_tokens: int = 2048
    llm_onboarding_max_tokens: int = 1024
    fast_onboarding: bool = True
    split_onboarding_phases: bool = True
    defer_memory_writes: bool = True
    skip_web_research: bool = False
    embedding_cache_size: int = 512

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

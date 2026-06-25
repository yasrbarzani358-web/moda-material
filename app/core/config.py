from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(..., validation_alias="TELEGRAM_BOT_TOKEN")
    admin_ids: str = Field(default="", validation_alias="ADMIN_IDS")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/ai_material_assistant.db",
        validation_alias="DATABASE_URL",
    )
    openai_api_key: str | None = Field(default=None, validation_alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", validation_alias="OPENAI_MODEL")
    enable_ai_generation: bool = Field(default=False, validation_alias="ENABLE_AI_GENERATION")
    public_base_url: str | None = Field(default=None, validation_alias="PUBLIC_BASE_URL")
    request_timeout_seconds: float = Field(default=15, validation_alias="REQUEST_TIMEOUT_SECONDS")
    max_results_per_source: int = Field(default=5, validation_alias="MAX_RESULTS_PER_SOURCE")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    generated_dir: Path = Path("generated")

    @property
    def admin_id_set(self) -> set[int]:
        if not self.admin_ids:
            return set()
        return {int(item.strip()) for item in self.admin_ids.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

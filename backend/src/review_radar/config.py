"""Runtime configuration, read from the environment only.

Secrets are `SecretStr` so they never end up in logs or reprs. Nothing here has
a real credential as a default; store and model integrations switch on only
when their variables are present.
"""

from functools import cached_property
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEMO = "demo"
DEFAULT_OPENAI_MODEL = "openai:gpt-5.4-mini"
DEFAULT_OPENAI_EMBEDDINGS = "openai:text-embedding-3-small"


class Settings(BaseSettings):
    # Empty values in .env mean "not set", so a copied .env.example is valid as is.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    database_url: str = (
        "postgresql+asyncpg://review_radar:review_radar@localhost:55432/review_radar"
    )

    model: str | None = Field(default=None, description="Any PydanticAI model id, or 'demo'.")
    embedding_model: str | None = None
    openai_api_key: SecretStr | None = None

    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:5173",
        "http://localhost:8080",
    ]

    triage_concurrency: int = Field(default=8, ge=1, le=64)
    llm_max_attempts: int = Field(default=3, ge=1, le=10)

    # Posting needs both store keys and this explicit switch, so configuring
    # read access for ingestion can never post a reply as a side effect.
    posting_enabled: bool = False

    app_store_app_id: str | None = None
    app_store_issuer_id: str | None = None
    app_store_key_id: str | None = None
    app_store_private_key: SecretStr | None = None
    app_store_private_key_path: Path | None = None

    google_play_package_name: str | None = None
    google_play_service_account_file: Path | None = None

    log_level: str = "INFO"
    log_json: bool = False

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @cached_property
    def resolved_model(self) -> str:
        if self.model:
            return self.model
        return DEFAULT_OPENAI_MODEL if self.openai_api_key else DEMO

    @cached_property
    def resolved_embedding_model(self) -> str:
        if self.embedding_model:
            return self.embedding_model
        if self.model and self.model != DEMO and not self.openai_api_key:
            # A non-OpenAI chat model without an embeddings choice: stay offline
            # for embeddings rather than guess a provider.
            return DEMO
        return DEFAULT_OPENAI_EMBEDDINGS if self.openai_api_key else DEMO

    @property
    def demo_mode(self) -> bool:
        return self.resolved_model == DEMO

    def app_store_key_pem(self) -> str | None:
        if self.app_store_private_key is not None:
            return self.app_store_private_key.get_secret_value()
        if self.app_store_private_key_path is not None:
            return self.app_store_private_key_path.read_text()
        return None

    @property
    def app_store_configured(self) -> bool:
        return bool(
            self.app_store_app_id
            and self.app_store_issuer_id
            and self.app_store_key_id
            and (self.app_store_private_key or self.app_store_private_key_path)
        )

    @property
    def google_play_configured(self) -> bool:
        return bool(self.google_play_package_name and self.google_play_service_account_file)

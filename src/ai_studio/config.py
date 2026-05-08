"""Application settings.

Loads from environment (.env in dev, GCP Secret Manager in prod). All external
service references go through here so tests can override via env vars.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AISTUDIO_", extra="ignore")

    # GCP
    gcp_project: str = Field(default="ai-influencer-studio-dev")
    gcs_bucket: str = Field(default="ai-influencer-studio-dev")
    cloud_sql_dsn: str = Field(default="postgresql+psycopg://localhost/ai_studio")

    # External APIs
    anthropic_api_key: str = Field(default="")
    modal_token_id: str = Field(default="")
    modal_token_secret: str = Field(default="")
    fal_api_key: str = Field(default="")

    # Instagram (per-persona tokens are stored in Secret Manager and looked up
    # by the reference string on the persona row).
    meta_app_id: str = Field(default="")
    meta_app_secret: str = Field(default="")

    # Behavior
    log_level: str = Field(default="INFO")
    candidate_count_default: int = Field(default=8)


def get_settings() -> Settings:
    return Settings()

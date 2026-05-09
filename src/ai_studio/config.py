"""Application settings.

Stack: Modal (GPU + Secrets + Cron) + Supabase (Postgres + file storage).
Loads from .env in dev; Modal Secrets in production.

DATABASE_URL defaults to SQLite for Phase 0-1 (zero setup).
Set to a Supabase Postgres URL for Phase 2+ multi-persona state.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AISTUDIO_", extra="ignore")

    # Database — SQLite by default (Phase 0-1), Supabase Postgres for Phase 2+
    # SQLite:   sqlite:///./studio.db
    # Supabase: postgresql+psycopg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
    database_url: str = Field(default="sqlite:///./studio.db")

    # Supabase — for file storage (generated images, Phase 2+)
    # Get from: supabase.com → project → Settings → API
    supabase_url: str = Field(default="")
    supabase_key: str = Field(default="")  # anon/service_role key

    # Modal — GPU compute, model volume, cron scheduling
    # Set via: modal token set --token-id ... --token-secret ...
    # Or fill .env for local dev.
    modal_token_id: str = Field(default="")
    modal_token_secret: str = Field(default="")

    # External APIs
    anthropic_api_key: str = Field(default="")
    fal_api_key: str = Field(default="")  # fal.ai fallback / Kling video

    # Instagram Graph API
    # Per-persona tokens are stored in Modal Secrets and looked up by the
    # secret_ref string on the persona row.
    meta_app_id: str = Field(default="")
    meta_app_secret: str = Field(default="")

    # Behaviour
    log_level: str = Field(default="INFO")
    candidate_count_default: int = Field(default=8)

    @property
    def using_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def using_supabase_storage(self) -> bool:
        return bool(self.supabase_url and self.supabase_key)


def get_settings() -> Settings:
    return Settings()

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    google_places_api_key: str | None = None
    tripadvisor_api_key: str | None = None

    # Per-review extraction runs on many reviews, so it uses a fast, low-cost model.
    extraction_model: str = "claude-haiku-5-5"
    # Final summary and "ask the reviews" answers.
    summary_model: str = "claude-sonnet-5-5"

    # SQLite for local development; docker-compose sets a Postgres URL
    # (postgresql+asyncpg://user:pass@host/db).
    database_url: str = "sqlite+aiosqlite:///./hotel.db"

    # Daily refresh of source scores (feeds the score-over-time chart). With
    # several API replicas, enable it on one only.
    daily_refresh: bool = True
    daily_refresh_hour_utc: int = 3

    # Comma-separated origins allowed to call the API (the Next.js frontend).
    cors_origins: str = "http://localhost:3000"
    cache_ttl_seconds: int = 6 * 60 * 60

    # Request limits that keep API costs bounded once the site is public (0 = off).
    # Per client IP; only new report builds count, cached reports are free.
    limit_search_per_minute: int = 30
    limit_builds_per_hour: int = 20
    limit_asks_per_hour: int = 30
    # For the whole server, so many visitors together cannot run up the Claude bill.
    limit_builds_per_day: int = 1000
    limit_asks_per_day: int = 3000
    # Set when the API runs behind a reverse proxy that sets X-Forwarded-For;
    # otherwise the header is ignored, because clients could fake it.
    trust_proxy: bool = False

    @property
    def demo_mode(self) -> bool:
        """Without source API keys the app serves a bundled fictional demo hotel."""
        return not (self.google_places_api_key or self.tripadvisor_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

"""Runtime settings, read from the environment or a local `.env`."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Everything the ETL needs to reach the portal."""

    # Socrata app token. Required -- CI supplies it from the ODP_API_KEY
    # repository secret.
    odp_api_key: SecretStr

    # Portal to snapshot. Any Socrata domain works.
    odp_domain: str = "data.ct.gov"

    # An asset whose data has not moved in this long is a pipeline question.
    stale_days: int = 365

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance - loaded once, reused everywhere."""
    return Settings()  # ty: ignore[missing-argument]

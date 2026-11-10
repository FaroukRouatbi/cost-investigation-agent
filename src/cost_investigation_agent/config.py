from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="COST_AGENT_",
        extra="ignore",
    )

    aws_region: str = "us-east-1"
    log_level: str = "INFO"
    max_steps: int = 10


@lru_cache
def get_settings() -> Settings:
    return Settings()

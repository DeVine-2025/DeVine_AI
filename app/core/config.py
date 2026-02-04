from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 경로 (app/core/config.py 기준으로 2단계 상위)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    OPENAI_API_KEY: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False  # True면 에러 상세 정보 노출


@lru_cache
def get_settings() -> Settings:
    return Settings()

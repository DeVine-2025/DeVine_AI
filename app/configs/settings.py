from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Gemini (Report Generation)
    gemini_api_key: str
    temp_dir: str = "./temp"

    # OpenAI (Embedding)
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    embedding_dimension: int = 1536

    # Internal API Key (Backend callback auth)
    internal_api_key: str = ""

    # Logging
    log_level: str = "INFO"
    log_dir: str = "./logs"
    debug: bool = False

    class Config:
        env_file = ".env"


settings = Settings()

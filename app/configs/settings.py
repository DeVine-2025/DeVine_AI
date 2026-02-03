from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gemini_api_key: str
    temp_dir: str = "./temp"

    class Config:
        env_file = ".env"


settings = Settings()

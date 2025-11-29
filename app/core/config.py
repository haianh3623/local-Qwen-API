from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Grading"
    API_V1_STR: str = "/api/v1"
    OLLAMA_HOST: str
    MODEL_NAME: str

    MAX_INPUT_TOKENS: int = 3000
    MAX_CONCURRENT_REQUESTS: int = 1

    SHARED_SECRET_KEY: Optional[str] = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
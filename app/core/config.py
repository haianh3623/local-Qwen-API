import os
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

    # --- RAG Settings ---
    # Lưu DB vào thư mục data để map volume Docker dễ dàng
    CHROMA_DB_DIR: str = os.path.join(os.getcwd(), "data", "chroma_db")
    RAG_EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    RAG_BATCH_SIZE: int = 50  # Giảm xuống 50 để cực kỳ an toàn cho RAM thấp
    RAG_CHUNK_SIZE: int = 500
    RAG_CHUNK_OVERLAP: int = 50

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
# Tạo thư mục DB nếu chưa có
os.makedirs(settings.CHROMA_DB_DIR, exist_ok=True)
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    telegram_api_id: int
    telegram_api_hash: str
    telegram_phone: str
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    openai_api_key: str
    embedding_model: str = "text-embedding-3-small"
    rag_answer_model: str = "gpt-4o-mini"
    rag_answer_context_tokens: int = 3000
    data_dir: str = "/app/data"
    session_dir: str = "/app/session"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

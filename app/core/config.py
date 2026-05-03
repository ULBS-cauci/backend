from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # These names must exactly match your .env file
    VECTOR_DB_TYPE: str
    QDRANT_HOST: str
    QDRANT_PORT: int
    QDRANT_SERVICE_API_KEY: Optional[str] = None

    # General Embedding Client Selection (e.g., "ollama", "openai")
    EMBEDDING_CLIENT_TYPE: str

    # Ollama embedding model settings
    OLLAMA_HOST: str
    OLLAMA_EMBED_MODEL: str
    
    # Relational DB Settings (PostgreSQL)
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@localhost:5432/{self.POSTGRES_DB}"

    # This tells Pydantic to look for the .env file in your root directory
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
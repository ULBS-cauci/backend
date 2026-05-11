from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Vector DB
    VECTOR_DB_TYPE: str
    VECTOR_DB_ENDPOINT: str
    VECTOR_DB_SERVICE_API_KEY: Optional[str] = None

    # Object Storage
    OBJECT_STORAGE_TYPE: str
    OBJECT_STORAGE_ENDPOINT: str
    OBJECT_STORAGE_ACCESS_KEY: str
    OBJECT_STORAGE_SECRET_KEY: str
    OBJECT_STORAGE_USE_SSL: bool = True

    # General Embedding Client Selection (e.g., "ollama", "openai")
    EMBEDDING_CLIENT_TYPE: str

    # Ollama embedding model settings
    OLLAMA_HOST: str
    OLLAMA_EMBED_MODEL: str

    # General LLM Client Selection (e.g., "openai", "ollama")
    LLM_CLIENT_TYPE: str

    # OpenAI LLM settings
    OPENAI_API_KEY: str
    OPENAI_LLM_MODEL: str = "gpt-4o-mini"
    LLM_TEMPERATURE: float = 0.2

    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Relational DB Settings (PostgreSQL)
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # This tells Pydantic to look for the .env file in your root directory
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

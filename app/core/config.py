from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class _Base(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


class AppSettings(_Base):
    """Provider selectors — controls which concrete client is wired per interface.
    All fields have defaults, so this class never raises a ValidationError at startup.
    """

    VECTOR_DB_CLIENT_TYPE: str = "qdrant"
    EMBEDDING_CLIENT_TYPE: str = "ollama"
    LLM_CLIENT_TYPE: str = "openai"
    OBJECT_STORAGE_CLIENT_TYPE: str = "minio"


class QdrantSettings(_Base):
    QDRANT_ENDPOINT: str
    QDRANT_API_KEY: Optional[str] = None


class OllamaSettings(_Base):
    OLLAMA_HOST: str
    OLLAMA_EMBED_MODEL: str


class OpenAISettings(_Base):
    OPENAI_API_KEY: str
    OPENAI_LLM_MODEL: str
    OPENAI_TEMPERATURE: float


class MinIOSettings(_Base):
    MINIO_ENDPOINT: str
    MINIO_USER: str
    MINIO_PASSWORD: str
    MINIO_USE_SSL: bool = False


class PostgresSettings(_Base):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_SSL: bool = False

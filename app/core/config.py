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

    ENVIRONMENT: str = "dev"
    VECTOR_DB_CLIENT_TYPE: str = "qdrant"
    EMBEDDING_CLIENT_TYPE: str = "ollama"
    LLM_CLIENT_TYPE: str = "openai"
    OBJECT_STORAGE_CLIENT_TYPE: str = "minio"
    RERANKER_CLIENT_TYPE: str = "cross-encoder"
    SPARSE_ENCODER_CLIENT_TYPE: str = "bge-m3"


class QdrantSettings(_Base):
    QDRANT_ENDPOINT: str
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_UPSERT_BATCH_SIZE: int = (
        256  # max points per upsert request (stays under Qdrant's 32 MiB cap)
    )


class OllamaSettings(_Base):
    OLLAMA_HOST: str
    OLLAMA_EMBED_MODEL: str
    OLLAMA_EMBED_BATCH_SIZE: int = 128  # max texts per Ollama embed request


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


class CrossEncoderSettings(_Base):
    CROSS_ENCODER_MODEL: str = "BAAI/bge-reranker-v2-m3"
    CROSS_ENCODER_SCORE_THRESHOLD: float = 0.0


class BM25Settings(_Base):
    BM25_MODEL: str = "Qdrant/bm25"


class BGEM3Settings(_Base):
    BGEM3_MODEL: str = "BAAI/bge-m3"


class ChunkingSettings(_Base):
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 100


class IngestionSettings(_Base):
    INGEST_BATCH_SIZE: int = (
        256  # chunks processed per pipeline batch (overlap unit + memory bound)
    )
class ExecutorSettings(_Base):
    """Controls the ThreadPoolExecutor used for background document ingestion."""
    INGESTION_MAX_WORKERS: int = 4


MINIO_MATERIALS_BUCKET = "materials"
MINIO_ATTACHMENTS_BUCKET = "chat-attachments"
QDRANT_MATERIALS_COLLECTION = "university_library"

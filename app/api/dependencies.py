from functools import lru_cache
from fastapi import Depends
from app.core.config import Settings
from app.data_access.clients.qdrant_client import QdrantClient
from app.data_access.interfaces.vector_db import VectorDBClient

from app.data_access.interfaces.embedding import IEmbeddingClient
from app.data_access.clients.embedding_client import OllamaEmbeddingClient

@lru_cache()
def get_settings() -> Settings:
    """Reads and caches the settings so they are only initialized once."""
    return Settings()

@lru_cache()
def _get_qdrant_client() -> QdrantClient:
    """Caches the Qdrant connection pool per application lifecycle."""
    settings = get_settings()
    return QdrantClient(
        host=settings.QDRANT_HOST,
        port=settings.QDRANT_PORT,
        api_key=settings.QDRANT_SERVICE_API_KEY
    )

def get_vector_db_client(settings: Settings = Depends(get_settings)) -> VectorDBClient:
    """Yields the configured Vector Database client."""
    if settings.VECTOR_DB_TYPE == "qdrant":
        return _get_qdrant_client()
    else:
        raise ValueError(f"Unsupported Vector Database type: {settings.VECTOR_DB_TYPE}")

@lru_cache()
def _get_ollama_client() -> IEmbeddingClient:
    """Caches the Ollama connection pool per application lifecycle."""
    settings = get_settings()
    return OllamaEmbeddingClient(
        host=settings.OLLAMA_HOST,
        model_name=settings.OLLAMA_EMBED_MODEL
    )

def get_embedding_client(settings: Settings = Depends(get_settings)) -> IEmbeddingClient:
    """
    Yields the configured Embedding client according to environment settings.
    Typed against the ABC interface to preserve complete DI flexibility.
    """
    if settings.EMBEDDING_CLIENT_TYPE == "ollama":
        return _get_ollama_client()
    else:
        raise ValueError(f"Unsupported Embedding Client type: {settings.EMBEDDING_CLIENT_TYPE}")


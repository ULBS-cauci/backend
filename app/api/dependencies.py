from functools import lru_cache
from fastapi import Depends
from app.core.config import Settings
from app.data_access.clients.qdrant_client import QdrantClient
from app.data_access.interfaces.vector_db import VectorDBInterface

from app.data_access.interfaces.embedding import IEmbeddingClient
from app.data_access.clients.embedding_client import OllamaEmbeddingClient

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from typing import AsyncGenerator
from app.data_access.interfaces.relational_db import IRelationalDB
from app.data_access.clients.postgres_client import PostgresClient

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

def get_vector_db_client(settings: Settings = Depends(get_settings)) -> VectorDBInterface:
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


@lru_cache()
def _get_async_engine() -> AsyncEngine:
    """
    Caches the SQLAlchemy/SQLModel AsyncEngine.
    The engine manages the connection pool to PostgreSQL and should only be created once.
    """
    settings = get_settings()
    return create_async_engine(settings.DATABASE_URL, echo=False)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Generates a fresh database session for each incoming request.
    Handles commit automatically on success, and rollback on failure.
    """
    engine = _get_async_engine()
    async with AsyncSession(engine) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

def get_relational_db(session: AsyncSession = Depends(get_db_session)) -> IRelationalDB:
    """
    Injects the active database session into the concrete Postgres client,
    but exposes it safely behind the generic IRelationalDB interface.
    """
    return PostgresClient(session)
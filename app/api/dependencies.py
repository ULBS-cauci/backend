from functools import lru_cache
from fastapi import Depends
from app.core.config import Settings
from app.data_access.clients.qdrant_client import QdrantClient
from app.data_access.interfaces.vector_db import VectorDBInterface

from app.data_access.interfaces.embedding import IEmbeddingClient
from app.data_access.clients.embedding_client import OllamaEmbeddingClient

from app.data_access.interfaces.llm import LLMInterface
from app.data_access.clients.openai_client import OpenAILLMClient

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.engine import URL  
from typing import AsyncGenerator


@lru_cache()
def get_settings() -> Settings:
    """Reads and caches the settings so they are only initialized once."""
    return Settings()


@lru_cache()
def _get_qdrant_client() -> QdrantClient:
    """Caches the Qdrant connection pool per application lifecycle."""
    settings = get_settings()
    return QdrantClient(
        endpoint=settings.VECTOR_DB_ENDPOINT, api_key=settings.VECTOR_DB_SERVICE_API_KEY
    )


def get_vector_db_client(
    settings: Settings = Depends(get_settings),
) -> VectorDBInterface:
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
        host=settings.OLLAMA_HOST, model_name=settings.OLLAMA_EMBED_MODEL
    )


@lru_cache()
def _get_openai_client() -> OpenAILLMClient:
    """Caches the OpenAI client per application lifecycle."""
    settings = get_settings()
    return OpenAILLMClient(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_LLM_MODEL,
        temperature=settings.LLM_TEMPERATURE,
    )


def get_llm_client(settings: Settings = Depends(get_settings)) -> LLMInterface:
    """
    Yields the configured LLM client according to environment settings.
    Typed against the ABC interface to preserve complete DI flexibility.
    """
    if settings.LLM_CLIENT_TYPE == "openai":
        return _get_openai_client()
    else:
        raise ValueError(f"Unsupported LLM Client type: {settings.LLM_CLIENT_TYPE}")


def get_embedding_client(
    settings: Settings = Depends(get_settings),
) -> IEmbeddingClient:
    """
    Yields the configured Embedding client according to environment settings.
    Typed against the ABC interface to preserve complete DI flexibility.
    """
    if settings.EMBEDDING_CLIENT_TYPE == "ollama":
        return _get_ollama_client()
    else:
        raise ValueError(
            f"Unsupported Embedding Client type: {settings.EMBEDDING_CLIENT_TYPE}"
        )

@lru_cache()
def _get_async_engine() -> AsyncEngine:
    """
    Caches the SQLAlchemy/SQLModel AsyncEngine.
    The engine manages the connection pool to PostgreSQL and should only be created once.
    """
    settings = get_settings()
    
    database_url = URL.create(
        drivername="postgresql+asyncpg",
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB
    )
    
    return create_async_engine(database_url, echo=False)

    
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Generates a fresh database session for each incoming request.
    Handles commit automatically on success, and rollback on failure.
    """
    engine = _get_async_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

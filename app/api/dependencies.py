from functools import lru_cache
from fastapi import Depends
from app.data_access.clients.qdrant_client import QdrantClient
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.core.config import (
    AppSettings,
    QdrantSettings,
    OllamaSettings,
    OpenAISettings,
    MinIOSettings,
    PostgresSettings,
)

from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.clients.embedding_client import OllamaEmbeddingClient

from app.data_access.interfaces.llm import LLMInterface
from app.data_access.clients.openai_client import OpenAILLMClient

from app.services.chat_service import ChatService
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.data_access.clients.minio_client import MinIOClient

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.engine import URL
from typing import AsyncGenerator

from app.services.file_service import FileService

from app.data_access.interfaces.text_splitter import TextSplitterInterface
from app.data_access.clients.langchain_splitter_client import LangChainRecursiveSplitterClient

@lru_cache()
def get_app_settings() -> AppSettings:
    """Reads and caches the provider-selector settings. Never raises — all fields have defaults."""
    return AppSettings()



@lru_cache()
def _get_qdrant_client() -> QdrantClient:
    """Caches the Qdrant connection pool per application lifecycle."""
    settings = QdrantSettings()
    return QdrantClient(
        endpoint=settings.QDRANT_ENDPOINT, api_key=settings.QDRANT_API_KEY
    )


def get_vector_db_client(
    app: AppSettings = Depends(get_app_settings),
) -> VectorDBInterface:
    """Yields the configured Vector Database client."""
    if app.VECTOR_DB_CLIENT_TYPE == "qdrant":
        return _get_qdrant_client()
    raise ValueError(f"Unsupported Vector Database type: {app.VECTOR_DB_CLIENT_TYPE}")


@lru_cache()
def _get_openai_llm_client() -> OpenAILLMClient:
    """Caches the OpenAI client per application lifecycle."""
    settings = OpenAISettings()
    return OpenAILLMClient(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_LLM_MODEL,
        temperature=settings.OPENAI_TEMPERATURE,
    )


def get_llm_client(app: AppSettings = Depends(get_app_settings)) -> LLMInterface:
    """Yields the configured LLM client. Typed against the ABC interface."""
    if app.LLM_CLIENT_TYPE == "openai":
        return _get_openai_llm_client()
    raise ValueError(f"Unsupported LLM Client type: {app.LLM_CLIENT_TYPE}")

@lru_cache()
def _get_ollama_embedding_client() -> OllamaEmbeddingClient:
    """Caches the Ollama embedding client per application lifecycle."""
    settings = OllamaSettings()
    return OllamaEmbeddingClient(
        host=settings.OLLAMA_HOST, model_name=settings.OLLAMA_EMBED_MODEL
    )

def get_embedding_client(
    app: AppSettings = Depends(get_app_settings),
) -> EmbeddingInterface:
    """Yields the configured Embedding client. Typed against the ABC interface."""
    if app.EMBEDDING_CLIENT_TYPE == "ollama":
        return _get_ollama_embedding_client()
    raise ValueError(f"Unsupported Embedding Client type: {app.EMBEDDING_CLIENT_TYPE}")

def get_chat_service(
    vector_db: VectorDBInterface = Depends(get_vector_db_client),
    embedding_client: EmbeddingInterface = Depends(get_embedding_client),
    llm_client: LLMInterface = Depends(get_llm_client)
) -> ChatService:
    return ChatService(vector_db=vector_db, embedding_client=embedding_client, llm_client=llm_client)


@lru_cache()
def _get_minio_client() -> MinIOClient:
    """Caches the MinIO session per application lifecycle."""
    settings = MinIOSettings()
    return MinIOClient(
        endpoint_url=settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_USER,
        secret_key=settings.MINIO_PASSWORD,
        use_ssl=settings.MINIO_USE_SSL,
    )


def get_object_storage_client(
    app: AppSettings = Depends(get_app_settings),
) -> ObjectStorageInterface:
    """Yields the configured Object Storage client."""
    if app.OBJECT_STORAGE_CLIENT_TYPE == "minio":
        return _get_minio_client()
    raise ValueError(
        f"Unsupported Object Storage type: {app.OBJECT_STORAGE_CLIENT_TYPE}"
    )

@lru_cache()
def _get_async_engine() -> AsyncEngine:
    """Caches the SQLAlchemy/SQLModel AsyncEngine. Created once per application lifecycle."""
    settings = PostgresSettings()
    
    database_url = URL.create(
        drivername="postgresql+asyncpg",
        username=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
    )

    return create_async_engine(
        database_url, 
        echo=False, 
        pool_pre_ping=True, 
        pool_size=5, 
        max_overflow=50,
        connect_args={"ssl": settings.POSTGRES_SSL}
    )

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Generates a fresh database session for each incoming request."""
    engine = _get_async_engine()
    async with AsyncSession(engine, expire_on_commit=False) as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_text_splitter() -> TextSplitterInterface:
    return LangChainRecursiveSplitterClient(chunk_size=1000, chunk_overlap=100)

def get_file_service(
    vector_db: VectorDBInterface = Depends(get_vector_db_client),
    embed_client: EmbeddingInterface = Depends(get_embedding_client),
    text_splitter: TextSplitterInterface = Depends(get_text_splitter), 
    db: AsyncSession = Depends(get_db_session)
) -> FileService:
    
    return FileService(
        vector_db=vector_db, 
        embed_client=embed_client, 
        text_splitter=text_splitter, 
        db=db
    )
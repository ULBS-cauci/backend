from functools import lru_cache
from fastapi import Depends, HTTPException, status
import uuid
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.data_access.clients.bm25_client import BM25SparseEncoder

from app.schemas.user_schemas import User, UserRole
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
from langchain_text_splitters import RecursiveCharacterTextSplitter


@lru_cache()
def get_app_settings() -> AppSettings:
    """Reads and caches the provider-selector settings. Never raises — all fields have defaults."""
    return AppSettings()  # type: ignore


@lru_cache()
def _get_qdrant_client() -> QdrantClient:
    """Caches the Qdrant connection pool per application lifecycle."""
    settings = QdrantSettings()  # type: ignore
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
    settings = OpenAISettings()  # type: ignore
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
    settings = OllamaSettings()  # type: ignore
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


@lru_cache()
def _get_minio_client() -> MinIOClient:
    """Caches the MinIO session per application lifecycle."""
    settings = MinIOSettings()  # type: ignore
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
    settings = PostgresSettings()  # type: ignore

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
        connect_args={"ssl": settings.POSTGRES_SSL},
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


async def get_current_user(
    db: AsyncSession = Depends(get_db_session),
    settings: AppSettings = Depends(get_app_settings),
) -> User:
    if settings.ENVIRONMENT != "dev":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                "Authentication is not implemented for non-dev environments. "
                "Configure real authentication before enabling these routes outside dev."
            ),
        )

    dummy_id = uuid.UUID("00000000-0000-0000-0000-000000000001")
    user = await db.get(User, dummy_id)
    if not user:
        user = User(
            id=dummy_id,
            email="dummy@student.com",
            first_name="Dummy",
            last_name="Student",
            hashed_password="dummy_password",
            role=UserRole.STUDENT,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    return user


@lru_cache()
def _get_bm25_sparse_encoder() -> BM25SparseEncoder:
    """Instantiates and caches the BM25 sparse encoder. Downloads vocabulary on first call."""
    return BM25SparseEncoder()


def get_sparse_encoder() -> SparseEncoderInterface:
    """Yields the configured sparse encoder. Typed against the ABC interface."""
    return _get_bm25_sparse_encoder()


def get_chat_service(
    vector_db: VectorDBInterface = Depends(get_vector_db_client),
    embedding_client: EmbeddingInterface = Depends(get_embedding_client),
    llm_client: LLMInterface = Depends(get_llm_client),
    sparse_encoder: SparseEncoderInterface = Depends(get_sparse_encoder),
    db_session: AsyncSession = Depends(get_db_session),
) -> ChatService:
    return ChatService(
        vector_db=vector_db,
        embedding_client=embedding_client,
        llm_client=llm_client,
        sparse_encoder=sparse_encoder,
        db_session=db_session,
    )


def get_file_service(
    vector_db: VectorDBInterface = Depends(get_vector_db_client),
    embed_client: EmbeddingInterface = Depends(get_embedding_client),
    sparse_encoder: SparseEncoderInterface = Depends(get_sparse_encoder),
    db: AsyncSession = Depends(get_db_session),
) -> FileService:
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    return FileService(
        vector_db=vector_db,
        embed_client=embed_client,
        sparse_encoder=sparse_encoder,
        text_splitter=splitter,
        db=db,
    )

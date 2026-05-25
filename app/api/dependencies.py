from functools import lru_cache
from fastapi import Depends, HTTPException, Request, status
from arq.connections import ArqRedis
import uuid
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.data_access.clients.bm25_client import BM25SparseEncoder
from app.data_access.clients.bge_m3_sparse_client import BGEM3SparseEncoder
from app.data_access.interfaces.reranker import RerankerInterface
from app.data_access.clients.cross_encoder_client import CrossEncoderReranker

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
    CrossEncoderSettings,
    BM25Settings,
    BGEM3Settings,
    ChunkingSettings,
)

def get_arq_pool(request: Request) -> ArqRedis:
    return request.app.state.arq_pool

from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.clients.embedding_client import OllamaEmbeddingClient

from app.data_access.interfaces.llm import LLMInterface
from app.data_access.clients.openai_client import OpenAILLMClient

from app.services.chat_service import ChatService
from app.services.course_service import CourseService
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
    return AppSettings()  # type: ignore


@lru_cache()
def _get_qdrant_client() -> QdrantClient:
    """Caches the Qdrant connection pool per application lifecycle."""
    settings = QdrantSettings()  # type: ignore
    return QdrantClient(
        endpoint=settings.QDRANT_ENDPOINT, api_key=settings.QDRANT_API_KEY
    )


def select_vector_db_client() -> VectorDBInterface:
    app = get_app_settings()
    if app.VECTOR_DB_CLIENT_TYPE == "qdrant":
        return _get_qdrant_client()
    raise ValueError(f"Unsupported Vector Database type: {app.VECTOR_DB_CLIENT_TYPE}")


def get_vector_db_client() -> VectorDBInterface:
    """Yields the configured Vector Database client."""
    return select_vector_db_client()


@lru_cache()
def _get_openai_llm_client() -> OpenAILLMClient:
    """Caches the OpenAI client per application lifecycle."""
    settings = OpenAISettings()  # type: ignore
    return OpenAILLMClient(
        api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_LLM_MODEL,
        temperature=settings.OPENAI_TEMPERATURE,
    )


def select_llm_client() -> LLMInterface:
    app = get_app_settings()
    if app.LLM_CLIENT_TYPE == "openai":
        return _get_openai_llm_client()
    raise ValueError(f"Unsupported LLM Client type: {app.LLM_CLIENT_TYPE}")


def get_llm_client() -> LLMInterface:
    """Yields the configured LLM client. Typed against the ABC interface."""
    return select_llm_client()


@lru_cache()
def _get_ollama_embedding_client() -> OllamaEmbeddingClient:
    """Caches the Ollama embedding client per application lifecycle."""
    settings = OllamaSettings()  # type: ignore
    return OllamaEmbeddingClient(
        host=settings.OLLAMA_HOST, model_name=settings.OLLAMA_EMBED_MODEL
    )


def select_embedding_client() -> EmbeddingInterface:
    app = get_app_settings()
    if app.EMBEDDING_CLIENT_TYPE == "ollama":
        return _get_ollama_embedding_client()
    raise ValueError(f"Unsupported Embedding Client type: {app.EMBEDDING_CLIENT_TYPE}")


def get_embedding_client() -> EmbeddingInterface:
    """Yields the configured Embedding client. Typed against the ABC interface."""
    return select_embedding_client()


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


@lru_cache()
def get_chunking_settings() -> ChunkingSettings:
    """Caches the chunking settings per application lifecycle."""
    return ChunkingSettings()  # type: ignore


@lru_cache()
def _get_text_splitter() -> LangChainRecursiveSplitterClient:
    """Caches the text splitter per application lifecycle."""
    chunking_settings = get_chunking_settings()
    return LangChainRecursiveSplitterClient(
        chunk_size=chunking_settings.CHUNK_SIZE,
        chunk_overlap=chunking_settings.CHUNK_OVERLAP,
    )


def select_text_splitter() -> TextSplitterInterface:
    return _get_text_splitter()


def get_text_splitter() -> TextSplitterInterface:
    """Yields the configured text splitter."""
    return _get_text_splitter()


def select_object_storage_client() -> ObjectStorageInterface:
    app = get_app_settings()
    if app.OBJECT_STORAGE_CLIENT_TYPE == "minio":
        return _get_minio_client()
    raise ValueError(f"Unsupported Object Storage type: {app.OBJECT_STORAGE_CLIENT_TYPE}")


def get_object_storage_client() -> ObjectStorageInterface:
    """Yields the configured Object Storage client."""
    return select_object_storage_client()


def _make_engine(pool_size: int, max_overflow: int) -> AsyncEngine:
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
        pool_size=pool_size,
        max_overflow=max_overflow,
        connect_args={"ssl": settings.POSTGRES_SSL},
    )


@lru_cache()
def _get_async_engine() -> AsyncEngine:
    """Caches the SQLAlchemy/SQLModel AsyncEngine. Created once per application lifecycle."""
    return _make_engine(pool_size=5, max_overflow=50)


@lru_cache()
def get_worker_db_engine() -> AsyncEngine:
    """Caches a smaller-pool engine for the ARQ worker process."""
    return _make_engine(pool_size=3, max_overflow=10)


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


def get_course_service(
    db: AsyncSession = Depends(get_db_session),
    object_storage: ObjectStorageInterface = Depends(get_object_storage_client),
    vector_db: VectorDBInterface = Depends(get_vector_db_client),
) -> CourseService:
    return CourseService(db=db, object_storage=object_storage, vector_db=vector_db)


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


async def get_dev_course(
    db: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    from app.schemas.course_schemas import Course

    dummy_id = uuid.UUID("00000000-0000-0000-0000-000000000002")
    course = await db.get(Course, dummy_id)
    if not course:
        course = Course(
            id=dummy_id,
            title="Dev Course",
            description="Auto-created dev course for testing.",
            held_by=current_user.id,
        )
        db.add(course)
        await db.commit()
        await db.refresh(course)
    return course


@lru_cache()
def _get_bm25_sparse_encoder() -> BM25SparseEncoder:
    """Instantiates and caches the BM25 sparse encoder. Downloads vocabulary on first call."""
    settings = BM25Settings()
    return BM25SparseEncoder(model_name=settings.BM25_MODEL)


@lru_cache()
def _get_bgem3_settings() -> BGEM3Settings:
    return BGEM3Settings()  # type: ignore


@lru_cache()
def _get_bgem3_sparse_encoder() -> BGEM3SparseEncoder:
    """Instantiates and caches the BGE-M3 sparse encoder. Downloads model on first call (~570MB)."""
    settings = _get_bgem3_settings()
    return BGEM3SparseEncoder(model_name=settings.BGEM3_MODEL)


def select_sparse_encoder() -> SparseEncoderInterface:
    app = get_app_settings()
    if app.SPARSE_ENCODER_CLIENT_TYPE == "bge-m3":
        return _get_bgem3_sparse_encoder()
    if app.SPARSE_ENCODER_CLIENT_TYPE == "bm25":
        return _get_bm25_sparse_encoder()
    raise ValueError(f"Unsupported sparse encoder type: {app.SPARSE_ENCODER_CLIENT_TYPE}")


def get_sparse_encoder() -> SparseEncoderInterface:
    """Yields the configured sparse encoder. Typed against the ABC interface."""
    return select_sparse_encoder()


@lru_cache()
def get_cross_encoder_settings() -> CrossEncoderSettings:
    """Reads and caches CrossEncoderSettings once per application lifecycle."""
    return CrossEncoderSettings()  # type: ignore


@lru_cache()
def _get_cross_encoder_reranker() -> CrossEncoderReranker:
    """Instantiates and caches the cross-encoder reranker. Downloads model on first call."""
    settings = get_cross_encoder_settings()
    return CrossEncoderReranker(model_name=settings.CROSS_ENCODER_MODEL)


def select_reranker() -> RerankerInterface:
    app = get_app_settings()
    if app.RERANKER_CLIENT_TYPE == "cross-encoder":
        return _get_cross_encoder_reranker()
    raise ValueError(f"Unsupported reranker type: {app.RERANKER_CLIENT_TYPE}")


def get_reranker() -> RerankerInterface:
    """Yields the configured reranker. Typed against the ABC interface."""
    return select_reranker()


def get_chat_service(
    vector_db: VectorDBInterface = Depends(get_vector_db_client),
    embedding_client: EmbeddingInterface = Depends(get_embedding_client),
    llm_client: LLMInterface = Depends(get_llm_client),
    sparse_encoder: SparseEncoderInterface = Depends(get_sparse_encoder),
    reranker: RerankerInterface = Depends(get_reranker),
    db_session: AsyncSession = Depends(get_db_session),
    cross_encoder_settings: CrossEncoderSettings = Depends(get_cross_encoder_settings),
) -> ChatService:
    return ChatService(
        vector_db=vector_db,
        embedding_client=embedding_client,
        llm_client=llm_client,
        sparse_encoder=sparse_encoder,
        reranker=reranker,
        score_threshold=cross_encoder_settings.CROSS_ENCODER_SCORE_THRESHOLD,
        db_session=db_session,
    )


def get_file_service(
    object_storage: ObjectStorageInterface = Depends(get_object_storage_client),
    db: AsyncSession = Depends(get_db_session),
    arq_pool: ArqRedis = Depends(get_arq_pool),
) -> FileService:
    return FileService(object_storage=object_storage, db=db, arq_pool=arq_pool)

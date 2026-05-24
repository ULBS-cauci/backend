import asyncio
import logging
import uuid
from functools import lru_cache

from arq.connections import RedisSettings as ArqRedisSettings
from docling.document_converter import DocumentConverter
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.engine import URL
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import (
    RedisSettings,
    QdrantSettings,
    OllamaSettings,
    MinIOSettings,
    PostgresSettings,
    ChunkingSettings,
    MATERIALS_BUCKET,
)
from app.data_access.clients.qdrant_client import QdrantClient
from app.data_access.clients.embedding_client import OllamaEmbeddingClient
from app.data_access.clients.minio_client import MinIOClient
from app.data_access.clients.markdown_splitter_client import MarkdownSplitterClient


from app.schemas.course_schemas import Course  
from app.schemas.user_schemas import User 
from app.schemas.chat_schemas import Conversation, Message, Attachment, SharedLink  # noqa: F401
from app.schemas.admin_schemas import SystemPrompt, LlmTip 
from app.schemas.knowledge_schemas import Material, IngestionStatus

from app.workers.ingestion_worker import extract_text_with_docling, create_document_chunks

logger = logging.getLogger(__name__)


@lru_cache()
def _worker_qdrant_client() -> QdrantClient:
    s = QdrantSettings()  # type: ignore
    return QdrantClient(endpoint=s.QDRANT_ENDPOINT, api_key=s.QDRANT_API_KEY)


@lru_cache()
def _worker_embedding_client() -> OllamaEmbeddingClient:
    s = OllamaSettings()  # type: ignore
    return OllamaEmbeddingClient(host=s.OLLAMA_HOST, model_name=s.OLLAMA_EMBED_MODEL)


@lru_cache()
def _worker_minio_client() -> MinIOClient:
    s = MinIOSettings()  # type: ignore
    return MinIOClient(
        endpoint_url=s.MINIO_ENDPOINT,
        access_key=s.MINIO_USER,
        secret_key=s.MINIO_PASSWORD,
        use_ssl=s.MINIO_USE_SSL,
    )


@lru_cache()
def _worker_text_splitter() -> MarkdownSplitterClient:
    s = ChunkingSettings()  # type: ignore
    return MarkdownSplitterClient(chunk_size=s.CHUNK_SIZE, chunk_overlap=s.CHUNK_OVERLAP)


@lru_cache()
def _worker_docling_converter() -> DocumentConverter:
    return DocumentConverter()


@lru_cache()
def _worker_db_engine() -> AsyncEngine:
    s = PostgresSettings()  # type: ignore
    url = URL.create(
        drivername="postgresql+asyncpg",
        username=s.POSTGRES_USER,
        password=s.POSTGRES_PASSWORD,
        host=s.POSTGRES_HOST,
        port=s.POSTGRES_PORT,
        database=s.POSTGRES_DB,
    )
    return create_async_engine(
        url,
        echo=False,
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=10,
        connect_args={"ssl": s.POSTGRES_SSL},
    )


async def startup(ctx: dict) -> None:
    logger.info("ARQ worker starting up...")
    minio = _worker_minio_client()
    await minio.connect()
    ctx["minio"] = minio
    ctx["qdrant"] = _worker_qdrant_client()
    ctx["embed"] = _worker_embedding_client()
    ctx["splitter"] = _worker_text_splitter()
    ctx["docling_converter"] = _worker_docling_converter()
    ctx["engine"] = _worker_db_engine()
    logger.info("ARQ worker clients ready.")


async def shutdown(ctx: dict) -> None:
    logger.info("ARQ worker shutting down...")
    minio: MinIOClient = ctx.get("minio")
    if minio:
        await minio.close()
    engine: AsyncEngine = ctx.get("engine")
    if engine:
        await engine.dispose()
    logger.info("ARQ worker shut down cleanly.")


async def process_document_task(
    ctx: dict,
    material_id: str,
    object_storage_key: str,
    filename: str,
) -> dict:
    """ARQ background task: download → extract → split → embed → upsert → update DB.

    Args:
        ctx:                ARQ worker context populated during startup.
        material_id:        UUID string of the Material DB record to update.
        object_storage_key: MinIO object key used to download the file.
        filename:           Original filename, used for format detection and metadata.

    Returns:
        A status dict with "status" and "material_id" keys on success.
    """
    mat_uuid: uuid.UUID = uuid.UUID(material_id)
    minio: MinIOClient = ctx["minio"]
    qdrant: QdrantClient = ctx["qdrant"]
    embed: OllamaEmbeddingClient = ctx["embed"]
    splitter: MarkdownSplitterClient = ctx["splitter"]
    docling_converter: DocumentConverter = ctx["docling_converter"]
    engine: AsyncEngine = ctx["engine"]

    async with AsyncSession(engine, expire_on_commit=False) as session:
        material: Material | None = await session.get(Material, mat_uuid)
        if not material:
            logger.error(f"Material {material_id} not found, aborting task.")
            return {"status": "not_found"}

        material.ingestion_status = IngestionStatus.PROCESSING
        session.add(material)
        await session.commit()

        collection_name: str = "university_library"
        vectors_written: bool = False
        try:
            content: bytes = await minio.download_file(MATERIALS_BUCKET, object_storage_key)

            full_text: str = await asyncio.to_thread(
                extract_text_with_docling, content, filename, docling_converter
            )

            text_chunks: list[str] = await asyncio.to_thread(splitter.split_text, full_text)
            text_chunks = list(dict.fromkeys(text_chunks))
            if not text_chunks:
                raise ValueError("Text splitting produced no chunks.")

            domain_chunks = await asyncio.to_thread(create_document_chunks, text_chunks, filename)

            vectors: list[list[float]] = await embed.embed_batch(text_chunks)
            if not vectors:
                raise ValueError(f"Embedding service returned no vectors for '{filename}'.")
            if len(vectors) != len(domain_chunks):
                raise ValueError("Number of embeddings does not match number of text chunks.")

            vector_size: int = len(vectors[0])
            await qdrant.create_collection(collection_name, vector_size, sparse=True)
            await qdrant.upsert_chunks(collection_name, domain_chunks, vectors)
            vectors_written = True

            await session.refresh(material)
            material.ingestion_status = IngestionStatus.COMPLETED
            session.add(material)
            await session.commit()
            logger.info(f"Material {material_id} ingestion COMPLETED.")
            return {"status": "completed", "material_id": material_id}

        except Exception as exc:
            logger.error(f"Ingestion failed for material {material_id}: {exc}", exc_info=True)
            if vectors_written:
                try:
                    await qdrant.delete_chunks_by_source(collection_name, filename)
                except Exception as rb_err:
                    logger.warning(f"Vector rollback failed for {material_id}: {rb_err}")

            await session.refresh(material)
            material.ingestion_status = IngestionStatus.FAILED
            material.ingestion_error = str(exc)[:2048]
            session.add(material)
            await session.commit()
            raise


class WorkerSettings:
    functions = [process_document_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
    redis_settings = ArqRedisSettings(
        host=RedisSettings().REDIS_HOST,
        port=RedisSettings().REDIS_PORT,
    )

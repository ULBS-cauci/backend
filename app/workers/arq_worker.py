import asyncio
import logging
import uuid

from arq.connections import RedisSettings as ArqRedisSettings
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import (
    RedisSettings,
    MATERIALS_BUCKET,
    QDRANT_MATERIALS_COLLECTION,
)
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.data_access.interfaces.text_splitter import TextSplitterInterface
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.core.providers import (
    get_worker_embed,
    get_worker_engine,
    get_worker_object_storage,
    get_worker_sparse_encoder,
    get_worker_text_splitter,
    get_worker_vector_db,
)

from app.schemas.course_schemas import Course
from app.schemas.user_schemas import User
from app.schemas.chat_schemas import Conversation, Message, Attachment, SharedLink  # noqa: F401
from app.schemas.admin_schemas import SystemPrompt, LlmTip
from app.schemas.knowledge_schemas import Material, IngestionStatus

from app.workers.ingestion_worker import extract_text_from_pdf, create_document_chunks

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    logger.info("ARQ worker starting up...")

    object_storage: ObjectStorageInterface = get_worker_object_storage()
    await object_storage.connect()
    ctx["object_storage"] = object_storage
    ctx["vector_db"] = get_worker_vector_db()
    ctx["embed"] = get_worker_embed()
    ctx["splitter"] = get_worker_text_splitter()

    logger.info("Loading sparse encoder model (downloads ~570MB on first run)...")
    ctx["sparse_encoder"] = await asyncio.to_thread(get_worker_sparse_encoder)
    logger.info("Sparse encoder ready.")

    ctx["engine"] = get_worker_engine()
    logger.info("ARQ worker clients ready.")


async def shutdown(ctx: dict) -> None:
    logger.info("ARQ worker shutting down...")
    object_storage: ObjectStorageInterface = ctx.get("object_storage")
    if object_storage:
        await object_storage.close()
    engine: AsyncEngine = ctx.get("engine")
    if engine:
        await engine.dispose()
    logger.info("ARQ worker shut down cleanly.")


async def process_pdf_task(
    ctx: dict,
    material_id: str,
    object_storage_key: str,
    filename: str,
) -> dict:
    mat_uuid = uuid.UUID(material_id)
    object_storage: ObjectStorageInterface = ctx["object_storage"]
    vector_db: VectorDBInterface = ctx["vector_db"]
    embed: EmbeddingInterface = ctx["embed"]
    splitter: TextSplitterInterface = ctx["splitter"]
    sparse_encoder: SparseEncoderInterface = ctx["sparse_encoder"]
    engine: AsyncEngine = ctx["engine"]

    async with AsyncSession(engine, expire_on_commit=False) as session:
        material = await session.get(Material, mat_uuid)
        if not material:
            logger.error(f"Material {material_id} not found, aborting task.")
            return {"status": "not_found"}

        material.ingestion_status = IngestionStatus.PROCESSING
        session.add(material)
        await session.commit()

        collection_name = QDRANT_MATERIALS_COLLECTION
        vectors_written = False
        try:
            content = await object_storage.download_file(MATERIALS_BUCKET, object_storage_key)

            full_text = await asyncio.to_thread(extract_text_from_pdf, content)
            if not full_text.strip():
                raise ValueError(f"Document {filename} contains no extractable text.")

            text_chunks = await asyncio.to_thread(splitter.split_text, full_text)
            if not text_chunks:
                raise ValueError("Could not create text chunks.")

            domain_chunks = await asyncio.to_thread(create_document_chunks, text_chunks, filename)

            vectors = await embed.embed_batch(text_chunks)
            if not vectors:
                raise ValueError(f"Embedding service returned no vectors for {filename}.")
            if len(vectors) != len(domain_chunks):
                raise ValueError("Number of embeddings does not match number of text chunks.")

            sparse_vectors = await sparse_encoder.encode_passages(text_chunks)

            vector_size = len(vectors[0])
            await vector_db.create_collection(collection_name, vector_size, sparse=True)
            await vector_db.upsert_chunks(collection_name, domain_chunks, vectors, sparse_vectors=sparse_vectors)
            vectors_written = True

            material.ingestion_status = IngestionStatus.COMPLETED
            material.vector_namespace = collection_name
            material.ingestion_error = None
            session.add(material)
            await session.commit()
            logger.info(f"Material {material_id} ingestion COMPLETED.")
            return {"status": "completed", "material_id": material_id}

        except Exception as exc:
            logger.error(f"Ingestion failed for material {material_id}: {exc}", exc_info=True)
            if vectors_written:
                try:
                    await vector_db.delete_chunks_by_source(collection_name, filename)
                except Exception as rb_err:
                    logger.warning(f"Vector rollback failed for {material_id}: {rb_err}")

            material.ingestion_status = IngestionStatus.FAILED
            material.ingestion_error = str(exc)[:2048]
            session.add(material)
            await session.commit()
            raise


_redis_settings = RedisSettings()


class WorkerSettings:
    functions = [process_pdf_task]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 4
    job_timeout = 600
    max_tries = 3
    redis_settings = ArqRedisSettings(
        host=_redis_settings.REDIS_HOST,
        port=_redis_settings.REDIS_PORT,
    )

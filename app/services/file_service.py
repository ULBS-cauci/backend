"""
FileService: handles document upload and background indexing.

Upload path (main event loop):
    1. Validate file extension
    2. Read bytes and upload to MinIO
    3. Create Material DB record (ingestion_status=PENDING)
    4. Submit _run_ingestion_in_thread to the ThreadPoolExecutor (fire-and-forget)
    5. Return MaterialPublic immediately

Background path (OS thread → fresh asyncio event loop):
    _run_ingestion_in_thread  →  asyncio.run(_async_ingestion(...))
        - Creates isolated DB engine (NullPool), MinIO client, embedding client,
          Qdrant client — all fresh, bound to the new event loop.
        - Reuses @lru_cache singletons for Docling converter, BGE-M3 encoder,
          Markdown splitter (thread-safe, no event-loop affinity).
        - Transitions Material: PENDING → RUNNING → COMPLETED | FAILED
"""
import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import UploadFile
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import (
    MINIO_MATERIALS_BUCKET,
    QDRANT_MATERIALS_COLLECTION,
    MinIOSettings,
    OllamaSettings,
    PostgresSettings,
    QdrantSettings,
)
from app.data_access.clients.embedding_client import OllamaEmbeddingClient
from app.data_access.clients.minio_client import MinIOClient
from app.data_access.clients.qdrant_client import QdrantClient as QdrantVectorClient
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.schemas.knowledge_schemas import IngestionStatus, Material, MaterialPublic
from app.workers.ingestion_worker import create_document_chunks, extract_text_with_docling

logger = logging.getLogger(__name__)

_MIME: dict[str, str] = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
}


def build_object_key(course_id: uuid.UUID, filename: str) -> str:
    return f"{course_id}/{uuid.uuid4()}_{filename}"


class FileService:
    def __init__(
        self,
        object_storage: ObjectStorageInterface,
        db: AsyncSession,
        executor: ThreadPoolExecutor,
    ) -> None:
        self.object_storage = object_storage
        self.db = db
        self.executor = executor

    async def upload_and_index(
        self,
        file: UploadFile,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MaterialPublic:
        filename: str = file.filename or "unnamed_document"
        suffix: str = Path(filename).suffix.lstrip(".").lower()

        if suffix not in _MIME:
            raise ValueError(
                f"Unsupported file type '.{suffix}'. "
                f"Accepted: {', '.join(sorted(_MIME))}"
            )

        content_type = _MIME[suffix]
        content = await file.read()
        object_key = build_object_key(course_id, filename)

        await self.object_storage.upload_file(
            MINIO_MATERIALS_BUCKET, object_key, content, content_type
        )

        material = Material(
            course_id=course_id,
            file_name=filename,
            file_type=suffix,
            vector_namespace=QDRANT_MATERIALS_COLLECTION,
            uploaded_by=user_id,
            object_storage_key=object_key,
            ingestion_status=IngestionStatus.PENDING,
        )
        self.db.add(material)
        await self.db.commit()
        await self.db.refresh(material)

        # Fire-and-forget: submit to thread pool. Pass only plain string primitives —
        # no async objects may cross the event-loop boundary.
        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            self.executor,
            FileService._run_ingestion_in_thread,
            str(material.id),
            object_key,
            filename,
        )

        return MaterialPublic.model_validate(material)

    @staticmethod
    def _run_ingestion_in_thread(
        material_id_str: str,
        object_storage_key: str,
        filename: str,
    ) -> None:
        """Sync wrapper. Creates a fresh event loop via asyncio.run().

        asyncio.run() is safe here because ThreadPoolExecutor workers are plain OS
        threads with no pre-existing event loop — unlike asyncio.to_thread() workers
        which inherit the parent loop.
        """
        try:
            asyncio.run(
                FileService._async_ingestion(material_id_str, object_storage_key, filename)
            )
        except Exception:
            logger.exception(
                f"[ingestion] unhandled error in thread for material {material_id_str}"
            )


    @staticmethod
    async def _async_ingestion(
        material_id_str: str,
        object_storage_key: str,
        filename: str,
    ) -> None:
        """Full ingestion pipeline running on a fresh event loop.

        Creates its own DB engine (NullPool — mandatory to avoid asyncpg event-loop
        conflicts), MinIO client, embedding client, and Qdrant client.
        Reuses @lru_cache singletons for heavy ML models (thread-safe).
        """
        # Import here to avoid circular imports at module level
        from app.api.dependencies import (
            _get_bgem3_sparse_encoder,
            _get_docling_converter,
            _get_markdown_splitter,
        )

        mat_id = uuid.UUID(material_id_str)

        pg = PostgresSettings()  
        db_url = URL.create(
            drivername="postgresql+asyncpg",
            username=pg.POSTGRES_USER,
            password=pg.POSTGRES_PASSWORD,
            host=pg.POSTGRES_HOST,
            port=pg.POSTGRES_PORT,
            database=pg.POSTGRES_DB,
        )
        engine = create_async_engine(
            db_url,
            poolclass=NullPool,
            connect_args={"ssl": pg.POSTGRES_SSL},
        )

        minio_s = MinIOSettings()  
        minio = MinIOClient(
            endpoint_url=minio_s.MINIO_ENDPOINT,
            access_key=minio_s.MINIO_USER,
            secret_key=minio_s.MINIO_PASSWORD,
            use_ssl=minio_s.MINIO_USE_SSL,
        )

        ollama_s = OllamaSettings()  
        embed_client = OllamaEmbeddingClient(
            host=ollama_s.OLLAMA_HOST,
            model_name=ollama_s.OLLAMA_EMBED_MODEL,
        )

        qdrant_s = QdrantSettings()  
        vector_db = QdrantVectorClient(
            endpoint=qdrant_s.QDRANT_ENDPOINT,
            api_key=qdrant_s.QDRANT_API_KEY,
        )

        converter     = _get_docling_converter()
        sparse_enc    = _get_bgem3_sparse_encoder()
        text_splitter = _get_markdown_splitter()

        async with AsyncSession(engine, expire_on_commit=False) as db:
            vectors_written: bool = False
            try:
                await minio.connect()

                material: Optional[Material] = await db.get(Material, mat_id)
                if material is None:
                    logger.error(
                        f"[ingestion] material {material_id_str} not found in DB — aborting."
                    )
                    return

                material.ingestion_status = IngestionStatus.RUNNING
                await db.commit()

                content: bytes = await minio.download_file(
                    MINIO_MATERIALS_BUCKET, object_storage_key
                )

                markdown: str = await asyncio.to_thread(
                    extract_text_with_docling, content, filename, converter
                )
                text_chunks: list[str] = await asyncio.to_thread(
                    text_splitter.split_text, markdown
                )
                text_chunks = list(dict.fromkeys(text_chunks))
                if not text_chunks:
                    raise ValueError("Text splitting produced no chunks.")

                domain_chunks = await asyncio.to_thread(
                    create_document_chunks, text_chunks, filename
                )

                dense_vectors = await embed_client.embed_batch(text_chunks)
                if not dense_vectors:
                    raise ValueError(f"Embedding service returned no vectors for '{filename}'.")
                if len(dense_vectors) != len(domain_chunks):
                    raise ValueError("Embedding count does not match chunk count.")

                sparse_vectors = await sparse_enc.encode_passages(text_chunks)

                vector_size = len(dense_vectors[0])
                await vector_db.create_collection(
                    QDRANT_MATERIALS_COLLECTION, vector_size, sparse=True
                )
                await vector_db.upsert_chunks(
                    QDRANT_MATERIALS_COLLECTION,
                    domain_chunks,
                    dense_vectors,
                    sparse_vectors=sparse_vectors,
                )
                vectors_written = True

                await db.refresh(material)
                material.ingestion_status = IngestionStatus.COMPLETED
                await db.commit()
                logger.info(
                    f"[ingestion] '{filename}' ({material_id_str}) completed successfully."
                )

            except Exception as exc:
                logger.exception(
                    f"[ingestion] '{filename}' ({material_id_str}) failed: {exc}"
                )

                if vectors_written:
                    try:
                        await vector_db.delete_chunks_by_source(
                            QDRANT_MATERIALS_COLLECTION, filename
                        )
                    except Exception as rb_err:
                        logger.warning(
                            f"[ingestion] vector rollback failed for {material_id_str}: {rb_err}"
                        )

                try:
                    material = await db.get(Material, mat_id)
                    if material:
                        material.ingestion_status = IngestionStatus.FAILED
                        material.ingestion_error = str(exc)[:500]
                        await db.commit()
                except Exception:
                    logger.exception(
                        f"[ingestion] could not write FAILED status for {material_id_str}"
                    )
            finally:
                await minio.close()
                await engine.dispose()

    async def get_materials_by_course(
        self, course_id: uuid.UUID
    ) -> list[MaterialPublic]:
        result = await self.db.exec(
            select(Material).where(Material.course_id == course_id)
        )
        materials = result.all()
        output: list[MaterialPublic] = []
        for material in materials:
            preview_url: Optional[str] = None
            if material.object_storage_key:
                preview_url = await self.object_storage.generate_presigned_url(
                    MINIO_MATERIALS_BUCKET, material.object_storage_key
                )
            public = MaterialPublic.model_validate(material)
            public.preview_url = preview_url
            output.append(public)
        return output

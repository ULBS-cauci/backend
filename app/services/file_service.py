"""
FileService: handles document upload and background indexing.

Upload path (main event loop):
    1. Validate file extension
    2. Read bytes and upload to MinIO
    3. Create Material DB record
    4. Submit _run_ingestion_in_thread to the ThreadPoolExecutor (fire-and-forget)
    5. Return MaterialPublic immediately

Background path (OS thread → fresh asyncio event loop):
    _run_ingestion_in_thread  →  asyncio.run(_async_ingestion(...))
        - Creates isolated DB engine (NullPool), MinIO client, embedding client,
          Qdrant client — all fresh, bound to the new event loop.
        - Reuses @lru_cache singletons for Docling converter, BGE-M3 encoder,
          Markdown splitter (thread-safe, no event-loop affinity).
"""
import asyncio
import logging
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional

from docling.document_converter import DocumentConverter
from fastapi import UploadFile
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession


from app.core.helpers import build_material_object_key
from app.core.config import (
    MINIO_MATERIALS_BUCKET,
    QDRANT_MATERIALS_COLLECTION,
    PostgresSettings,
)
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.data_access.interfaces.text_splitter import TextSplitterInterface
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.schemas.knowledge_schemas import Material, MaterialPublic
from app.workers.ingestion_worker import create_document_chunks, extract_text_with_docling

logger = logging.getLogger(__name__)

_CONTENT_TYPE_BY_EXTENSION: dict[str, str] = {
    "pdf":  "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "png":  "image/png",
    "jpg":  "image/jpeg",
    "jpeg": "image/jpeg",
}

class FileService:
    def __init__(
        self,
        object_storage: ObjectStorageInterface,
        db: AsyncSession,
        executor: ThreadPoolExecutor,
        make_ingestion_object_storage: Callable[[], ObjectStorageInterface],
        make_ingestion_embedding: Callable[[], EmbeddingInterface],
        make_ingestion_vector_db: Callable[[], VectorDBInterface],
        get_ingestion_sparse_encoder: Callable[[], SparseEncoderInterface],
        get_ingestion_document_converter: Callable[[], DocumentConverter],
        get_ingestion_text_splitter: Callable[[], TextSplitterInterface],
    ) -> None:
        self.object_storage = object_storage
        self.db = db
        self.executor = executor
        self._make_object_storage = make_ingestion_object_storage
        self._make_embedding = make_ingestion_embedding
        self._make_vector_db = make_ingestion_vector_db
        self._get_sparse_encoder = get_ingestion_sparse_encoder
        self._get_document_converter = get_ingestion_document_converter
        self._get_text_splitter = get_ingestion_text_splitter

    async def upload_and_index(
        self,
        file: UploadFile,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> MaterialPublic:
        filename: str = file.filename or ""
        suffix: str = Path(filename).suffix.lstrip(".").lower()

        if not suffix:
            _ct_to_ext: dict[str, str] = {mime: ext for ext, mime in _CONTENT_TYPE_BY_EXTENSION.items()}
            suffix = _ct_to_ext.get(file.content_type or "", "")
            if suffix:
                filename = f"unnamed_document.{suffix}" if not filename else f"{filename}.{suffix}"
            else:
                filename = filename or "unnamed_document"

        if suffix not in _CONTENT_TYPE_BY_EXTENSION:
            raise ValueError(
                f"Unsupported file type '.{suffix}'. "
                f"Accepted: {', '.join(sorted(_CONTENT_TYPE_BY_EXTENSION))}"
            )

        content_type = _CONTENT_TYPE_BY_EXTENSION[suffix]
        content = await file.read()
        material_id = uuid.uuid4()
        object_key = build_material_object_key(course_id, material_id, filename)

        await self.object_storage.upload_file(
            MINIO_MATERIALS_BUCKET, object_key, content, content_type
        )

        try:
            material = Material(
                id=material_id,
                course_id=course_id,
                file_name=filename,
                file_type=suffix,
                vector_namespace=QDRANT_MATERIALS_COLLECTION,
                uploaded_by=user_id,
                object_storage_key=object_key,
            )
            self.db.add(material)
            await self.db.commit()
            await self.db.refresh(material)
        except Exception:
            try:
                await self.object_storage.delete_file(MINIO_MATERIALS_BUCKET, object_key)
            except Exception as del_err:
                logger.warning(
                    "[upload] MinIO cleanup failed for orphaned object '%s': %s",
                    object_key, del_err,
                )
            raise

        loop = asyncio.get_running_loop()
        loop.run_in_executor(
            self.executor,
            FileService._run_ingestion_in_thread,
            str(material.id),
            object_key,
            filename,
            self._make_object_storage,
            self._make_embedding,
            self._make_vector_db,
            self._get_sparse_encoder,
            self._get_document_converter,
            self._get_text_splitter,
        )

        return MaterialPublic.model_validate(material)

    @staticmethod
    def _run_ingestion_in_thread(
        material_id_str: str,
        object_storage_key: str,
        filename: str,
        make_object_storage: Callable[[], ObjectStorageInterface],
        make_embedding: Callable[[], EmbeddingInterface],
        make_vector_db: Callable[[], VectorDBInterface],
        get_sparse_encoder: Callable[[], SparseEncoderInterface],
        get_document_converter: Callable[[], DocumentConverter],
        get_text_splitter: Callable[[], TextSplitterInterface],
    ) -> None:
        """Sync wrapper. Creates a fresh event loop via asyncio.run().

        asyncio.run() is safe here because ThreadPoolExecutor workers are plain OS
        threads with no pre-existing event loop.
        """
        try:
            asyncio.run(
                FileService._async_ingestion(
                    material_id_str,
                    object_storage_key,
                    filename,
                    make_object_storage,
                    make_embedding,
                    make_vector_db,
                    get_sparse_encoder,
                    get_document_converter,
                    get_text_splitter,
                )
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
        make_object_storage: Callable[[], ObjectStorageInterface],
        make_embedding: Callable[[], EmbeddingInterface],
        make_vector_db: Callable[[], VectorDBInterface],
        get_sparse_encoder: Callable[[], SparseEncoderInterface],
        get_document_converter: Callable[[], DocumentConverter],
        get_text_splitter: Callable[[], TextSplitterInterface],
    ) -> None:
        """Full ingestion pipeline running on a fresh event loop.

        Creates its own DB engine (NullPool — mandatory to avoid asyncpg event-loop
        conflicts). All other clients are provided via factory callables injected through
        the constructor, keeping concrete provider selection inside dependencies.py.
        Reuses @lru_cache singletons for heavy ML models (thread-safe, no event-loop affinity).
        """
        mat_id = uuid.UUID(material_id_str)

        pg = PostgresSettings()  # type: ignore
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

        minio: ObjectStorageInterface = make_object_storage()
        embed_client: EmbeddingInterface = make_embedding()
        vector_db: VectorDBInterface = make_vector_db()
        sparse_enc: SparseEncoderInterface = get_sparse_encoder()
        converter: DocumentConverter = get_document_converter()
        text_splitter: TextSplitterInterface = get_text_splitter()

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

                content: bytes = await minio.download_file(
                    MINIO_MATERIALS_BUCKET, object_storage_key
                )

                markdown: str = await asyncio.to_thread(
                    extract_text_with_docling, content, filename, converter
                )
                text_chunks: list[str] = text_splitter.split_text(markdown)
                text_chunks = list(dict.fromkeys(text_chunks))
                if not text_chunks:
                    raise ValueError("Text splitting produced no chunks.")

                domain_chunks = create_document_chunks(text_chunks, object_storage_key)

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
                            QDRANT_MATERIALS_COLLECTION, object_storage_key
                        )
                    except Exception as rb_err:
                        logger.warning(
                            f"[ingestion] vector rollback failed for {material_id_str}: {rb_err}"
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

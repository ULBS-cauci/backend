import uuid
import asyncio
from fastapi import UploadFile
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import IngestionSettings
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.schemas.knowledge_schemas import Material, MaterialPublic
from app.core.config import MINIO_MATERIALS_BUCKET, QDRANT_MATERIALS_COLLECTION
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.data_access.interfaces.text_splitter import TextSplitterInterface
from app.workers.ingestion_worker import (
    extract_text_from_pdf,
    create_document_chunks
)


def build_object_key(course_id: uuid.UUID, filename: str) -> str:
    return f"{course_id}/{uuid.uuid4()}_{filename}"


class FileService:
    def __init__(
        self,
        vector_db: VectorDBInterface,
        embed_client: EmbeddingInterface,
        object_storage: ObjectStorageInterface,
        sparse_encoder: SparseEncoderInterface,
        text_splitter: TextSplitterInterface,
        db: AsyncSession,
        ingestion_settings: IngestionSettings
    ):
        self.vector_db = vector_db
        self.embed_client = embed_client
        self.object_storage = object_storage
        self.sparse_encoder = sparse_encoder        
        self.text_splitter = text_splitter
        self.db = db
        self.ingestion_settings = ingestion_settings

    async def upload_and_index(
        self, file: UploadFile, course_id: uuid.UUID, user_id: uuid.UUID
    ) -> MaterialPublic:
        filename = file.filename or "unnamed_document.pdf"
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted.")

        content = await file.read()
        object_key = build_object_key(course_id, filename)

        collection_name = await self.process_and_index_pdf(content, filename)

        uploaded = False
        try:
            await self.object_storage.upload_file(
                MINIO_MATERIALS_BUCKET, object_key, content, "application/pdf"
            )
            uploaded = True

            material = Material(
                course_id=course_id,
                file_name=filename,
                file_type="pdf",
                vector_namespace=collection_name,
                uploaded_by=user_id,
                object_storage_key=object_key,
            )
            self.db.add(material)
            await self.db.commit()
            await self.db.refresh(material)
            return MaterialPublic.model_validate(material)
        except Exception:
            await self.vector_db.delete_chunks_by_source(collection_name, filename)
            if uploaded:
                await self.object_storage.delete_file(
                    MINIO_MATERIALS_BUCKET, object_key
                )
            raise

    async def process_and_index_pdf(self, content: bytes, filename: str) -> str:
        try:
            full_text = await asyncio.to_thread(extract_text_from_pdf, content)
        except ValueError as exc:
            error_message = str(exc)
            if error_message == "PDF contains no extractable text":
                raise ValueError(
                    f"Document {filename} contains no extractable text."
                ) from exc
            raise ValueError(
                f"Failed to process document {filename}: {error_message}"
            ) from exc

        # Use injected text splitter with configured chunk size/overlap
        text_chunks = await asyncio.to_thread(
            self.text_splitter.split_text,
            full_text
        )

        if not text_chunks:
            raise ValueError("Could not create text chunks.")

        domain_chunks = await asyncio.to_thread(
            create_document_chunks, text_chunks, filename
        )

        collection_name = QDRANT_MATERIALS_COLLECTION

        # Determine the embedding dimension once, up front, so the collection can be created
        # before the first batch is upserted. create_collection is idempotent (no-op if exists).
        probe_vector = await self.embed_client.embed_text(text_chunks[0])
        await self.vector_db.create_collection(
            collection_name, len(probe_vector), sparse=True
        )

        batch_size = self.ingestion_settings.INGEST_BATCH_SIZE
        for start in range(0, len(domain_chunks), batch_size):
            end = min(start + batch_size, len(domain_chunks))
            batch_chunks = domain_chunks[start:end]
            batch_texts = text_chunks[start:end]

            # Dense (Ollama, async network) and sparse (BGE-M3, asyncio.to_thread) run concurrently.
            dense_vectors, sparse_vectors = await asyncio.gather(
                self.embed_client.embed_batch(batch_texts),
                self.sparse_encoder.encode_passages(batch_texts),
            )

            if len(dense_vectors) != len(batch_chunks):
                raise ValueError(
                    "Number of embeddings does not match number of chunks in batch."
                )

            await self.vector_db.upsert_chunks(
                collection_name,
                batch_chunks,
                dense_vectors,
                sparse_vectors=sparse_vectors,
            )

        return collection_name

    async def get_materials_by_course(
        self, course_id: uuid.UUID
    ) -> list[MaterialPublic]:
        result = await self.db.exec(
            select(Material).where(Material.course_id == course_id)
        )
        materials = result.all()
        output = []
        for material in materials:
            preview_url = None
            if material.object_storage_key:
                preview_url = await self.object_storage.generate_presigned_url(
                    MINIO_MATERIALS_BUCKET, material.object_storage_key
                )
            public = MaterialPublic.model_validate(material)
            public.preview_url = preview_url
            output.append(public)
        return output

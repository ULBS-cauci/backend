import io
import uuid
import asyncio
from fastapi import UploadFile
from sqlmodel import select
from pypdf import PdfReader
from sqlmodel.ext.asyncio.session import AsyncSession
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.schemas.vector_schemas import DocumentChunk
from app.schemas.knowledge_schemas import Material, MaterialPublic

MATERIALS_BUCKET = "materials"


class FileService:
    def __init__(
        self,
        vector_db: VectorDBInterface,
        embed_client: EmbeddingInterface,
        text_splitter: RecursiveCharacterTextSplitter,
        object_storage: ObjectStorageInterface,
        db: AsyncSession,
    ):
        self.vector_db = vector_db
        self.embed_client = embed_client
        self.splitter = text_splitter
        self.object_storage = object_storage
        self.db = db

    def _extract_text_from_pdf(self, content: bytes) -> str:
        pdf = PdfReader(io.BytesIO(content))
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(page_texts)

    async def upload_and_index(
        self, file: UploadFile, course_id: uuid.UUID, user_id: uuid.UUID
    ) -> MaterialPublic:
        filename = file.filename or "unnamed_document.pdf"
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted.")

        content = await file.read()

        object_key = f"{course_id}/{uuid.uuid4()}_{filename}"
        await self.object_storage.upload_file(
            MATERIALS_BUCKET, object_key, content, "application/pdf"
        )

        collection_name = await self.process_and_index_pdf(content, filename)

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

    async def process_and_index_pdf(self, content: bytes, filename: str) -> str:
        full_text = await asyncio.to_thread(self._extract_text_from_pdf, content)
        if not full_text.strip():
            raise ValueError(f"Document {filename} contains no extractable text.")

        text_chunks = self.splitter.split_text(full_text)
        if not text_chunks:
            raise ValueError("Could not create text chunks.")

        domain_chunks = [
            DocumentChunk(
                id=str(uuid.uuid4()), text=text, metadata={"source": filename}
            )
            for text in text_chunks
        ]

        vectors = await self.embed_client.embed_batch(text_chunks)

        if not vectors:
            raise ValueError(
                f"Embedding service returned no vectors for document {filename}."
            )

        collection_name = "university_library"
        vector_size = len(vectors[0])

        if len(vectors) != len(domain_chunks):
            raise ValueError(
                "Number of embeddings does not match number of text chunks."
            )

        await self.vector_db.create_collection(collection_name, vector_size)
        await self.vector_db.upsert_chunks(collection_name, domain_chunks, vectors)

        return collection_name

    async def get_materials_by_course(self, course_id: uuid.UUID) -> list[MaterialPublic]:
        result = await self.db.exec(
            select(Material).where(Material.course_id == course_id)
        )
        materials = result.all()
        output = []
        for material in materials:
            preview_url = None
            if material.object_storage_key:
                preview_url = await self.object_storage.generate_presigned_url(
                    MATERIALS_BUCKET, material.object_storage_key
                )
            public = MaterialPublic.model_validate(material)
            public.preview_url = preview_url
            output.append(public)
        return output

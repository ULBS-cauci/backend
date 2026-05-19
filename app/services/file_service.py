import uuid
import asyncio
from fastapi import UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import ChunkingSettings
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.schemas.vector_schemas import DocumentChunk
from app.schemas.knowledge_schemas import Material
from app.workers.ingestion_worker import (
    extract_text_from_pdf,
    split_text_into_chunks,
    create_document_chunks
)

class FileService:
    def __init__(
        self,
        vector_db: VectorDBInterface,
        embed_client: EmbeddingInterface,
        sparse_encoder: SparseEncoderInterface,
        text_splitter: RecursiveCharacterTextSplitter,
        db: AsyncSession,
        chunking_settings: ChunkingSettings
    ):
        self.vector_db = vector_db
        self.embed_client = embed_client
        self.sparse_encoder = sparse_encoder
        self.splitter = text_splitter
        self.db = db
        self.chunking_settings = chunking_settings
        

    async def upload_and_index(self, file: UploadFile, course_id: uuid.UUID, user_id: uuid.UUID) -> str: 
        filename = file.filename or "unnamed_document.pdf"
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted.")
            
        content = await file.read()
        collection_name = await self.process_and_index_pdf(content, filename)
        
        # TODO: Save Material record once authentication is implemented
        # This will track the file in the database with user_id and course_id
        
        return collection_name

    async def process_and_index_pdf(self, content: bytes, filename: str) -> str:
        full_text = await asyncio.to_thread(extract_text_from_pdf, content)
        
        text_chunks = await asyncio.to_thread(
            split_text_into_chunks, 
            full_text, 
            self.chunking_settings.CHUNK_SIZE,
            self.chunking_settings.CHUNK_OVERLAP
        )

        if not text_chunks:
            raise ValueError("Could not create text chunks.")

        domain_chunks = await asyncio.to_thread(
            create_document_chunks,
            text_chunks,
            filename
        )

        dense_vectors = await self.embed_client.embed_batch(text_chunks)

        if not dense_vectors:
            raise ValueError(f"Embedding service returned no vectors for document {filename}.")
        if len(dense_vectors) != len(domain_chunks):
            raise ValueError("Number of embeddings does not match number of text chunks.")

        sparse_vectors = await self.sparse_encoder.encode_passages(text_chunks)

        collection_name = "university_library"
        vector_size = len(dense_vectors[0])

        await self.vector_db.create_collection(collection_name, vector_size, sparse=True)
        await self.vector_db.upsert_chunks(
            collection_name, domain_chunks, dense_vectors, sparse_vectors=sparse_vectors
        )

        return collection_name
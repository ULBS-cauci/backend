import uuid
import asyncio
from fastapi import UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.text_splitter import TextSplitterInterface
from app.workers.ingestion_worker import (
    extract_text_from_pdf,
    create_document_chunks
)

class FileService:
    def __init__(
        self, 
        vector_db: VectorDBInterface, 
        embed_client: EmbeddingInterface,
        text_splitter: TextSplitterInterface,
        db: AsyncSession
    ):
        self.vector_db = vector_db
        self.embed_client = embed_client
        self.text_splitter = text_splitter
        self.db = db 

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
        
        if not full_text.strip():
            raise ValueError(f"Document {filename} contains no extractable text.")
        
        # Use injected text splitter with configured chunk size/overlap
        text_chunks = await asyncio.to_thread(
            self.text_splitter.split_text,
            full_text
        )

        if not text_chunks:
            raise ValueError("Could not create text chunks.")

        domain_chunks = await asyncio.to_thread(
            create_document_chunks,
            text_chunks,
            filename
        )

        vectors = await self.embed_client.embed_batch(text_chunks)

        # Guard against embedding service returning no vectors
        if not vectors:
            raise ValueError(f"Embedding service returned no vectors for document {filename}.")
        
        # Ensure vectors and chunks align
        if len(vectors) != len(domain_chunks):
            raise ValueError("Number of embeddings does not match number of text chunks.")
        
        collection_name = "university_library"
        vector_size = len(vectors[0])
        
        await self.vector_db.create_collection(collection_name, vector_size)
        await self.vector_db.upsert_chunks(collection_name, domain_chunks, vectors)
        
        return collection_name
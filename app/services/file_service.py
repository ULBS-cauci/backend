import io
import uuid
import asyncio
from fastapi import UploadFile
from pypdf import PdfReader
from sqlmodel.ext.asyncio.session import AsyncSession
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface
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
        embed_client: EmbeddingInterface    ,
        text_splitter: RecursiveCharacterTextSplitter,
        db: AsyncSession  
    ):
        self.vector_db = vector_db
        self.embed_client = embed_client
        self.splitter = text_splitter
        self.db = db

    async def upload_and_index(self, file: UploadFile, course_id: uuid.UUID, user_id: uuid.UUID) -> str: 
        filename = file.filename or "unnamed_document.pdf"
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted.")

        content = await file.read()
        collection_name = await self.process_and_index_pdf(content, filename)
        
        # TODO: Create Material record when real course_id and user_id are available
        # For now, skip database insert to test PDF ingestion and Qdrant integration
        # material = Material(
        #     course_id=course_id,
        #     file_name=filename,
        #     file_type="pdf",
        #     vector_namespace=collection_name,
        #     uploaded_by=user_id
        # )
        # self.db.add(material)
        # await self.db.flush()
        # await self.db.refresh(material)
        
        return collection_name

    async def process_and_index_pdf(self, content: bytes, filename: str) -> str:
        """
        Process PDF: extract text, split into chunks, embed, and index to Qdrant.
        Heavy lifting (PDF parsing, chunking) is delegated to worker threads.
        """
        full_text = await asyncio.to_thread(extract_text_from_pdf, content)
        
        text_chunks = await asyncio.to_thread(
            split_text_into_chunks, 
            full_text,
            1000,  # chunk_size
            100    # chunk_overlap
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

        collection_name = "university_library"
        vector_size = len(vectors[0])

        # Ensure vectors and chunks align
        if len(vectors) != len(domain_chunks):
            raise ValueError("Number of embeddings does not match number of text chunks.")

        await self.vector_db.create_collection(collection_name, vector_size)
        await self.vector_db.upsert_chunks(collection_name, domain_chunks, vectors)

        return collection_name
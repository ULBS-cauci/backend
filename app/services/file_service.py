import io
import uuid
import asyncio
from fastapi import UploadFile
from pypdf import PdfReader
from sqlmodel.ext.asyncio.session import AsyncSession

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import IEmbeddingClient
from app.schemas.vector_schemas import DocumentChunk, DocumentMetadata

class FileService:
    def __init__(
        self, 
        vector_db: VectorDBInterface, 
        embed_client: IEmbeddingClient,
        text_splitter
    ):
        self.vector_db = vector_db
        self.embed_client = embed_client
        self.splitter = text_splitter

    def _extract_text_from_pdf(self, content: bytes) -> str:
        """Private synchronous method for CPU-heavy processing."""
        pdf = PdfReader(io.BytesIO(content))
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        return "".join(page_texts)

    async def upload_and_index(self, file: UploadFile, db: AsyncSession) -> str:
        """
        Orchestrates validation, processing, and metadata storage.
        """
        if not file.filename.endswith(".pdf"):
            raise ValueError("Only PDF files are accepted.")

        content = await file.read()
        
        collection = await self.process_and_index_pdf(content, file.filename)
        
        new_doc = DocumentMetadata(
            filename=file.filename,
            qdrant_collection=collection
        )
        db.add(new_doc)
        await db.flush() 
        await db.refresh(new_doc)
        
        return collection

    async def process_and_index_pdf(self, content: bytes, filename: str) -> str:
        """
        Transforms PDF content into vectors and saves them in Qdrant.
        """
   
        full_text = await asyncio.to_thread(self._extract_text_from_pdf, content)

        if not full_text.strip():
            raise ValueError(f"Document {filename} contains no extractable text.")

        text_chunks = self.splitter.split_text(full_text)
        
        if not text_chunks:
            raise ValueError("Could not create text chunks from this document.")

        domain_chunks = [
            DocumentChunk(
                id=str(uuid.uuid4()), 
                text=text, 
                metadata={"source": filename}
            ) for text in text_chunks
        ]

        vectors = await self.embed_client.embed_batch(text_chunks)

        if not vectors:
            raise ValueError("Error generating embeddings for the document.")

        collection_name = "university_library"
        vector_size = len(vectors[0])
        
        await self.vector_db.create_collection(collection_name, vector_size)
        await self.vector_db.upsert_chunks(collection_name, domain_chunks, vectors)

        return collection_name
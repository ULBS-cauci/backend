import io
import uuid
import asyncio
from fastapi import UploadFile
from pypdf import PdfReader
from sqlmodel.ext.asyncio.session import AsyncSession
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import EmbeddingInterface
from app.schemas.vector_schemas import DocumentChunk, DocumentMetadata

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

    def _extract_text_from_pdf(self, content: bytes) -> str:
        pdf = PdfReader(io.BytesIO(content))
        page_texts = [page.extract_text() or "" for page in pdf.pages]
        return "\n\n".join(page_texts)

    async def upload_and_index(self, file: UploadFile) -> str: 
        filename = file.filename or "unnamed_document.pdf"
        if not filename.lower().endswith(".pdf"):
            raise ValueError("Only PDF files are accepted.")

        content = await file.read()
        collection_name = await self.process_and_index_pdf(content, filename)
        
        new_doc = DocumentMetadata(
            filename=filename,
            qdrant_collection=collection_name
        )
        self.db.add(new_doc)
        await self.db.flush() 
        await self.db.refresh(new_doc)
        
        return collection_name

    async def process_and_index_pdf(self, content: bytes, filename: str) -> str:
        full_text = await asyncio.to_thread(self._extract_text_from_pdf, content)
        if not full_text.strip():
            raise ValueError(f"Document {filename} contains no extractable text.")

        text_chunks = self.splitter.split_text(full_text)
        if not text_chunks:
            raise ValueError("Could not create text chunks.")

        domain_chunks = [
            DocumentChunk(
                id=str(uuid.uuid4()), 
                text=text, 
                metadata={"source": filename}
            ) for text in text_chunks
        ]

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
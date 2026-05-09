import io
import uuid
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.data_access.interfaces.embedding import IEmbeddingClient
from app.schemas.vector_schemas import DocumentChunk

class FileService:
    def __init__(self, vector_db: VectorDBInterface, embed_client: IEmbeddingClient):
        self.vector_db = vector_db
        self.embed_client = embed_client
        self.splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

    async def process_and_index_pdf(self, content: bytes, filename: str) -> str:
        """
        Transform a PDF file into text, generate vectors, and save them in Qdrant.
        """
        pdf = PdfReader(io.BytesIO(content))
        full_text = ""
        for page in pdf.pages:
            full_text += page.extract_text() or ""

        text_chunks = self.splitter.split_text(full_text)

        domain_chunks = []
        for text in text_chunks:
            domain_chunks.append(
                DocumentChunk(
                    id=str(uuid.uuid4()), 
                    text=text, 
                    metadata={"source": filename}
                )
            )

        vectors = await self.embed_client.embed_batch(text_chunks)

        collection_name = "university_library"
        vector_size = len(vectors[0])
        
        await self.vector_db.create_collection(collection_name, vector_size)
        await self.vector_db.upsert_chunks(collection_name, domain_chunks, vectors)

        return collection_name
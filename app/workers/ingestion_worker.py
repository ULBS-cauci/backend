"""
Synchronous worker for heavy PDF processing tasks.
These functions run in a thread pool to avoid blocking the async event loop.
"""

import io
import uuid
from typing import List
from pypdf import PdfReader
from app.schemas.vector_schemas import DocumentChunk


def extract_text_from_pdf(content: bytes) -> str:
    """
    Synchronous function to extract text from PDF content.
    Designed to run in a thread pool via asyncio.to_thread()

    Args:
        content: Raw PDF file bytes

    Returns:
        Extracted text from all PDF pages

    Raises:
        ValueError: If PDF cannot be read or contains no text
    """
    try:
        pdf = PdfReader(io.BytesIO(content))
        if not pdf.pages:
            raise ValueError("PDF contains no pages")

        page_texts = [page.extract_text() or "" for page in pdf.pages]
        full_text = "\n\n".join(page_texts)

        if not full_text.strip():
            raise ValueError("PDF contains no extractable text")

        return full_text
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}") from e


def create_document_chunks(
    text_chunks: List[str], filename: str
) -> List[DocumentChunk]:
    """
    Synchronous function to create DocumentChunk objects.
    Designed to run in a thread pool via asyncio.to_thread()

    Args:
        text_chunks: List of text chunks
        filename: Source filename for metadata

    Returns:
        List of DocumentChunk objects
    """
    chunks = []
    for text in text_chunks:
        chunk = DocumentChunk(id=uuid.uuid4(), text=text, metadata={"source": filename})
        chunks.append(chunk)

    return chunks

"""
Synchronous worker utilities for heavy document processing.

All public functions in this module are designed to run inside a thread pool
(via asyncio.to_thread() or concurrent.futures.ThreadPoolExecutor) to avoid
blocking the async event loop.
"""

import io
import logging
import os
import tempfile
import uuid
from pathlib import Path
from typing import List

from docling.document_converter import DocumentConverter

from app.schemas.vector_schemas import DocumentChunk

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES: frozenset[str] = frozenset(
    {".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg"}
)


def extract_text_with_docling(
    content: bytes,
    filename: str,
    converter: DocumentConverter,
) -> str:
    """Convert any supported document to Markdown using a pre-initialised Docling converter.

    Writes bytes to a NamedTemporaryFile (preserving the original file extension so Docling
    selects the correct backend), runs the conversion, then deletes the temp file in a
    finally block regardless of success or failure.

    This function is synchronous and CPU-bound. Always call it via:
        await asyncio.to_thread(extract_text_with_docling, content, filename, converter)

    Args:
        content:   Raw file bytes downloaded from object storage.
        filename:  Original filename; used to determine the format suffix and to produce
                   informative error messages.
        converter: A pre-warmed DocumentConverter instance.  Reusing one instance avoids
                   the multi-second ML model loading cost on every job.

    Returns:
        The document's full text as a Markdown string.

    Raises:
        ValueError: If the file extension is unsupported, or if Docling produces an empty
                    Markdown output.
    """
    suffix: str = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(
            f"Unsupported file format '{suffix}'. "
            f"Accepted: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    tmp_path: str = ""
    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        logger.info("[docling] converting '%s' (%d bytes) ...", filename, len(content))
        result = converter.convert(tmp_path)
        markdown: str = result.document.export_to_markdown()

        if not markdown.strip():
            raise ValueError(f"Document '{filename}' contains no extractable text.")

        logger.info("[docling] '%s' → %d chars of Markdown.", filename, len(markdown))
        return markdown
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def create_document_chunks(
    text_chunks: List[str],
    source: str,
) -> List[DocumentChunk]:
    """Map a list of text strings to DocumentChunk objects.

    Each chunk receives a fresh UUID and a metadata dict carrying the source key,
    which is used later for targeted vector deletion.

    Args:
        text_chunks: List of text strings produced by the text splitter.
        source:      Unique identifier stored in each chunk's metadata — should be the
                     object_storage_key (e.g. ``<course_id>/<uuid>_filename.pdf``) so
                     that rollback deletions are scoped to this exact upload and never
                     accidentally remove chunks from a different material with the same
                     filename.

    Returns:
        List of DocumentChunk objects ready for embedding and upsert.
    """
    chunks = [
        DocumentChunk(
            id=uuid.uuid4(),
            text=chunk,
            metadata={"source": source},
        )
        for chunk in text_chunks
    ]
    logger.debug("[chunks] created %d DocumentChunks (source=%s)", len(chunks), source)
    return chunks

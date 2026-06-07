"""
Shared logic for serving a *previewable* version of a stored file.

PDFs and images are served as-is. DOCX/PPTX are converted to PDF with headless
LibreOffice (so the browser can render them inline) and the result is cached in
object storage keyed by the file's immutable id, so only the first preview pays
the conversion cost. If conversion isn't possible, the original bytes are served
so the client can still offer a download.
"""
import asyncio
import io
import logging
from pathlib import Path
from typing import AsyncGenerator, Union

from app.core.helpers import content_type_for_filename
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.workers.pdf_converter import (
    CONVERTIBLE_SUFFIXES,
    convert_office_to_pdf,
    libreoffice_available,
)

logger = logging.getLogger(__name__)

PreviewBody = Union[AsyncGenerator[bytes, None], io.BytesIO]


async def get_previewable(
    storage: ObjectStorageInterface,
    bucket: str,
    object_key: str,
    filename: str,
    cache_key: str,
) -> tuple[str, PreviewBody]:
    """Return (media_type, body) for an inline preview of the stored object."""
    suffix = Path(filename).suffix.lower()

    # Non-Office files (pdf, images, anything else) are already browser-friendly
    # or have no inline renderer — stream them unchanged.
    if suffix not in CONVERTIBLE_SUFFIXES or not libreoffice_available():
        return (
            content_type_for_filename(filename),
            storage.stream_file(bucket, object_key),
        )

    # Serve a previously converted PDF if we have one cached.
    if await storage.file_exists(bucket, cache_key):
        return "application/pdf", storage.stream_file(bucket, cache_key)

    # First preview: convert, cache, and serve. Any failure falls back to the
    # original bytes so the client degrades to a download instead of erroring.
    try:
        original = await storage.download_file(bucket, object_key)
        pdf_bytes = await asyncio.to_thread(convert_office_to_pdf, original, filename)
        await storage.upload_file(bucket, cache_key, pdf_bytes, "application/pdf")
        return "application/pdf", io.BytesIO(pdf_bytes)
    except Exception as exc:
        logger.warning("PDF preview conversion failed for '%s': %s", filename, exc)
        return (
            content_type_for_filename(filename),
            storage.stream_file(bucket, object_key),
        )

"""
Synchronous worker for converting Office documents (docx/pptx) to PDF using
headless LibreOffice, so they can be previewed inline in the browser.

This is a blocking, subprocess-spawning operation and MUST run off the event
loop — call it via asyncio.to_thread(). Requires the `soffice` binary on PATH
(install LibreOffice; see backend/app/Readme.md).
"""
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Extensions this worker can convert to PDF.
CONVERTIBLE_SUFFIXES: frozenset[str] = frozenset({".docx", ".pptx"})

_SOFFICE_BIN = shutil.which("soffice") or shutil.which("libreoffice")
_CONVERT_TIMEOUT_SECONDS = 60


def libreoffice_available() -> bool:
    return _SOFFICE_BIN is not None


def convert_office_to_pdf(data: bytes, filename: str) -> bytes:
    """Convert docx/pptx bytes to PDF bytes via headless LibreOffice.

    Raises:
        RuntimeError: if LibreOffice is unavailable or the conversion fails.
    """
    if _SOFFICE_BIN is None:
        raise RuntimeError("LibreOffice (soffice) is not installed; cannot convert to PDF.")

    suffix = Path(filename).suffix.lower()
    if suffix not in CONVERTIBLE_SUFFIXES:
        raise RuntimeError(f"Cannot convert '{suffix}' to PDF.")

    # Each invocation gets its own temp dir + LibreOffice user profile so that
    # concurrent conversions don't clash over a shared profile.
    with tempfile.TemporaryDirectory(prefix="lo_pdf_") as tmp:
        tmp_path = Path(tmp)
        input_path = tmp_path / f"input{suffix}"
        input_path.write_bytes(data)
        profile_dir = tmp_path / "profile"

        try:
            result = subprocess.run(
                [
                    _SOFFICE_BIN,
                    f"-env:UserInstallation=file://{profile_dir}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp_path),
                    str(input_path),
                ],
                capture_output=True,
                timeout=_CONVERT_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"LibreOffice conversion timed out for '{filename}'.") from exc

        output_path = input_path.with_suffix(".pdf")
        if result.returncode != 0 or not output_path.exists():
            stderr = result.stderr.decode("utf-8", "replace").strip()
            raise RuntimeError(
                f"LibreOffice failed to convert '{filename}' "
                f"(exit {result.returncode}): {stderr or 'no output produced'}"
            )

        pdf_bytes = output_path.read_bytes()

    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError(f"Conversion of '{filename}' did not produce a valid PDF.")
    return pdf_bytes

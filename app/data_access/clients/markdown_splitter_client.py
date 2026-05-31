"""
Markdown-aware text splitter for Docling output.

Docling converts documents (PDF, DOCX, PPTX, images) to Markdown, preserving
structural information (headers, tables, lists, code fences). Using a Markdown-aware
splitter instead of a generic recursive splitter ensures chunks break at semantic
boundaries (heading boundaries, horizontal rules, blank-line paragraphs) before
falling back to character-level splits.
"""
from typing import List

from langchain_text_splitters import MarkdownTextSplitter

from app.data_access.interfaces.text_splitter import TextSplitterInterface


class MarkdownSplitterClient(TextSplitterInterface):
    """Markdown-aware text splitter for Docling output.

    Wraps LangChain's MarkdownTextSplitter with the project's TextSplitterInterface.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        self._splitter = MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split_text(self, text: str) -> List[str]:
        """Split Markdown text into chunks at semantic boundaries.

        Args:
            text: Markdown string produced by Docling's export_to_markdown().

        Returns:
            List of non-empty text chunks.

        Raises:
            ValueError: If splitting produces no output (empty or whitespace-only input).
        """
        chunks = self._splitter.split_text(text)
        if not chunks:
            raise ValueError("Markdown splitting produced no chunks.")
        return chunks

from typing import List

from langchain_text_splitters import MarkdownTextSplitter

from app.data_access.interfaces.text_splitter import TextSplitterInterface


class MarkdownSplitterClient(TextSplitterInterface):
    """Markdown-aware text splitter for Docling output.

    Uses LangChain's MarkdownTextSplitter, which splits on structural boundaries
    (headers, horizontal rules, code fences, blank-line paragraphs) before
    falling back to character-level splits. This preserves semantic coherence
    for documents converted to Markdown by Docling.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        self._splitter = MarkdownTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

    def split_text(self, text: str) -> List[str]:
        chunks = self._splitter.split_text(text)
        if not chunks:
            raise ValueError("Markdown splitting produced no chunks.")
        return chunks

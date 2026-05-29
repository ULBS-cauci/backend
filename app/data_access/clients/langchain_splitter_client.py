from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.data_access.interfaces.text_splitter import TextSplitterInterface

class LangChainRecursiveSplitterClient(TextSplitterInterface):
    """Concrete implementation of TextSplitterInterface using LangChain's RecursiveCharacterTextSplitter.
    
    This class encapsulates the logic for splitting text into chunks using LangChain's splitter."""
    
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 100) -> None:
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )

    def split_text(self, text: str) -> List[str]:
        chunks = self.splitter.split_text(text)
        if not chunks:
            raise ValueError("Text splitting produced no chunks")
        return chunks

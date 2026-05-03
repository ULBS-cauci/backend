from abc import ABC, abstractmethod
from typing import List

class IEmbeddingClient(ABC):
    """
    Abstract Base Class for Embedding generation.
    Any custom integration (Ollama, OpenAI, Claude, etc.) must implement these methods.
    """
    
    @abstractmethod
    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embeddings for a single piece of text.
        
        Args:
            text (str): The input string to embed.
            
        Returns:
            List[float]: The resulting embedding vector.
        """
        pass

    @abstractmethod
    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a batch of strings.
        Useful for document ingestion or fast processing of chunks.
        
        Args:
            texts (List[str]): Multiple strings to embed.
            
        Returns:
            List[List[float]]: A list of embedding vectors corresponding to the input texts.
        """
        pass

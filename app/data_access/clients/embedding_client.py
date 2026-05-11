import asyncio
from typing import List

import ollama
from app.data_access.interfaces.embedding import EmbeddingInterface

class OllamaEmbeddingClient(EmbeddingInterface):
    """
    Concrete implementation of EmbeddingInterface using the native ollama Python SDK.
    Strictly asynchronous.
    """
    def __init__(self, host: str, model_name: str):
        self.host = host
        self.model_name = model_name
        self.client = ollama.AsyncClient(host=self.host)

    async def embed_text(self, text: str) -> List[float]:
        """
        Embeds a single string using Ollama.
        """
        response = await self.client.embeddings(
            model=self.model_name,
            prompt=text
        )
        return response["embedding"]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a batch of strings concurrently using Ollama.
        """
        # Execute embeddings concurrently to maximize throughput
        tasks = [self.embed_text(chunk) for chunk in texts]
        return await asyncio.gather(*tasks)

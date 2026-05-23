from typing import List

import ollama
from app.data_access.interfaces.embedding import EmbeddingInterface


class OllamaEmbeddingClient(EmbeddingInterface):
    """
    Concrete implementation of EmbeddingInterface using the native ollama Python SDK.
    Strictly asynchronous.
    """

    def __init__(self, host: str, model_name: str, batch_size: int = 128):
        self.host = host
        self.model_name = model_name
        self.batch_size = batch_size
        self.client = ollama.AsyncClient(host=self.host)

    async def embed_text(self, text: str) -> List[float]:
        """
        Embeds a single string using Ollama.
        """
        response = await self.client.embeddings(
            model=self.model_name,
            prompt=text,
        )
        return response["embedding"]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds texts in bounded sub-batches so a single request never grows unbounded.
        Sub-requests are sequential: a single local Ollama instance serializes model compute,
        so concurrency yields little and risks overloading it. Order is preserved.
        """
        if not texts:
            return []
        all_vectors: List[List[float]] = []
        for start in range(0, len(texts), self.batch_size):
            sub = texts[start : start + self.batch_size]
            response = await self.client.embed(model=self.model_name, input=sub)
            all_vectors.extend(response.embeddings)
        return all_vectors

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
        response = await self.client.embed(
            model=self.model_name,
            input=text
        )
        return response.embeddings[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embeds a batch of strings using Ollama's batch embed endpoint.
        Sends all texts in a single HTTP request instead of N individual ones,
        eliminating round-trip overhead for large batches.
        Note: Ollama still processes each text sequentially on the model side —
        the speedup here is purely from removing HTTP overhead (~5-10s on 1000+ chunks).
        """
        response = await self.client.embed(
            model=self.model_name,
            input=texts,
        )
        return response.embeddings

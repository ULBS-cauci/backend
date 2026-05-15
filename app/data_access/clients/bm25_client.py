import asyncio
from typing import List

from fastembed.sparse import BM25

from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.schemas.vector_schemas import SparseVectorSchema


class BM25SparseEncoder(SparseEncoderInterface):
    """
    Concrete implementation of SparseEncoderInterface using fastembed's BM25.
    BM25 is CPU-bound and synchronous, so all calls are offloaded to a thread pool.
    """

    def __init__(self) -> None:
        self._encoder = BM25()

    async def encode_passages(self, texts: List[str]) -> List[SparseVectorSchema]:
        def _run() -> List[SparseVectorSchema]:
            embeddings = list(self._encoder.passage_embed(texts))
            return [
                SparseVectorSchema(
                    indices=emb.indices.tolist(),
                    values=emb.values.tolist(),
                )
                for emb in embeddings
            ]

        return await asyncio.to_thread(_run)

    async def encode_query(self, text: str) -> SparseVectorSchema:
        def _run() -> SparseVectorSchema:
            emb = next(iter(self._encoder.query_embed(text)))
            return SparseVectorSchema(
                indices=emb.indices.tolist(),
                values=emb.values.tolist(),
            )

        return await asyncio.to_thread(_run)

from abc import ABC, abstractmethod
from typing import List

from app.schemas.vector_schemas import SparseVectorSchema


class SparseEncoderInterface(ABC):
    """
    Abstract Base Class for sparse vector encoding.
    Any implementation (BM25, SPLADE, etc.) must implement these methods.

    passage_encode and query_encode are intentionally separate — sparse encoders
    apply different term-weighting at index time vs. query time.
    """

    @abstractmethod
    async def encode_passages(self, texts: List[str]) -> List[SparseVectorSchema]:
        """
        Encode a batch of document passages into sparse vectors for indexing.

        Args:
            texts: The document chunks to encode.

        Returns:
            One SparseVectorSchema per input text, in the same order.
        """
        pass

    @abstractmethod
    async def encode_query(self, text: str) -> SparseVectorSchema:
        """
        Encode a single query string into a sparse vector for search.

        Args:
            text: The user's query.

        Returns:
            A SparseVectorSchema representing the query's sparse weights.
        """
        pass

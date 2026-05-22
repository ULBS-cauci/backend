from abc import ABC, abstractmethod
from typing import List

from app.schemas.vector_schemas import SearchResult


class RerankerInterface(ABC):
    """
    Abstract Base Class for reranking retrieved chunks.
    Any implementation (CrossEncoder, Cohere Rerank API, etc.) must implement rerank().
    """

    @abstractmethod
    async def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_n: int = 5,
    ) -> List[SearchResult]:
        """
        Score each (query, chunk) pair and return the top_n most relevant results.

        Args:
            query: The original user question.
            results: Candidate chunks from retrieval (typically RRF fusion output).
            top_n: Number of results to return after reranking.

        Returns:
            Up to top_n SearchResult items sorted by descending reranker score.
        """
        pass

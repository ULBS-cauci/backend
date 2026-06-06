import asyncio
import logging
import time
from typing import List

import torch
from sentence_transformers import CrossEncoder

from app.data_access.interfaces.reranker import RerankerInterface
from app.schemas.vector_schemas import SearchResult

logger = logging.getLogger("uvicorn.error")


class CrossEncoderReranker(RerankerInterface):
    """
    Concrete implementation of RerankerInterface using sentence-transformers CrossEncoder.
    CrossEncoder.predict() is synchronous and CPU-bound — all calls are offloaded to a thread pool.
    """

    def __init__(self, model_name: str) -> None:
        self._model = CrossEncoder(model_name)

    async def rerank(
        self,
        query: str,
        results: List[SearchResult],
        top_n: int = 5,
    ) -> List[SearchResult]:
        if not results:
            return []

        def _run() -> List[SearchResult]:
            pairs = [(query, res.chunk.text) for res in results]
            t0 = time.perf_counter()
            # Force Sigmoid so scores are always relevance probabilities in [0, 1],
            # regardless of the model's default activation. Some cross-encoders (e.g.
            # ms-marco-MiniLM) emit raw logits by default, which would make the
            # downstream CROSS_ENCODER_SCORE_THRESHOLD gate meaningless.
            scores = self._model.predict(pairs, activation_fn=torch.nn.Sigmoid())
            elapsed = time.perf_counter() - t0
            ranked = sorted(zip(scores, results), key=lambda x: x[0], reverse=True)
            logger.debug(
                f"Reranker: scored {len(pairs)} pairs in {elapsed * 1000:.1f} ms; "
                f"top score={float(ranked[0][0]):.4f}"
            )
            return [
                SearchResult(chunk=res.chunk, score=float(score))
                for score, res in ranked[:top_n]
            ]

        return await asyncio.to_thread(_run)

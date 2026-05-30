import uuid
from typing import List, Dict

from app.schemas.vector_schemas import SearchResult, DocumentChunk


def rrf_fuse(
    semantic_results: List[SearchResult],
    keyword_results: List[SearchResult],
    k: int = 60,
    limit: int = 5,
) -> List[SearchResult]:
    """
    Reciprocal Rank Fusion over a semantic (dense) and a keyword (BM25 sparse) result list.

    Each chunk's RRF score is the sum of 1/(k + rank) across both lists.
    Chunks appearing in both lists accumulate scores from both, naturally
    ranking them higher. k=60 is the standard constant from the original paper.

    Args:
        semantic_results: Ranked results from the dense (embedding) search leg.
        keyword_results: Ranked results from the sparse (BM25) search leg.
        k: Smoothing constant — prevents high sensitivity to top ranks.
        limit: Number of top results to return after fusion.

    Returns:
        Up to `limit` SearchResult items sorted by descending RRF score.
    """
    scores: Dict[uuid.UUID, float] = {}
    chunks: Dict[uuid.UUID, DocumentChunk] = {}

    for ranked_list in (semantic_results, keyword_results):
        for rank, result in enumerate(ranked_list, start=1):
            chunk_id = result.chunk.id
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
            chunks[chunk_id] = result.chunk

    sorted_ids = sorted(scores, key=lambda cid: scores[cid], reverse=True)

    return [
        SearchResult(chunk=chunks[cid], score=scores[cid]) for cid in sorted_ids[:limit]
    ]

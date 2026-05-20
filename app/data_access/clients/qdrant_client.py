import uuid
from typing import List, Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    PointStruct, VectorParams, Distance, Filter, FieldCondition, MatchValue, FilterSelector,
    SparseVectorParams, SparseIndexParams, SparseVector, ScoredPoint,
)

from app.data_access.interfaces.vector_db import VectorDBInterface
from app.schemas.vector_schemas import DocumentChunk, SearchResult, SparseVectorSchema


class QdrantClient(VectorDBInterface):
    def __init__(self, endpoint: str, api_key: Optional[str] = None):
        self.client = AsyncQdrantClient(url=endpoint, api_key=api_key)

    async def create_collection(self, collection_name: str, vector_size: int, sparse: bool = False) -> bool:
        if await self.client.collection_exists(collection_name=collection_name):
            info = await self.client.get_collection(collection_name)
            vectors_cfg = info.config.params.vectors
            if not isinstance(vectors_cfg, dict) or "dense" not in vectors_cfg:
                raise ValueError(
                    f"Collection '{collection_name}' exists with a legacy unnamed-vector schema. "
                    "Drop it and re-upload all documents to migrate to the named-vector schema."
                )
            return False

        if sparse:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
                sparse_vectors_config={"sparse": SparseVectorParams(
                    index=SparseIndexParams(on_disk=False)
                )},
            )
        else:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
            )
        return True

    async def delete_collection(self, collection_name: str) -> bool:
        if not await self.client.collection_exists(collection_name=collection_name):
            return False

        await self.client.delete_collection(collection_name=collection_name)
        return True

    def _map_points_to_results(self, points: List[ScoredPoint]) -> List[SearchResult]:
        results = []
        for point in points:
            payload = point.payload or {}
            chunk = DocumentChunk(
                id=uuid.UUID(str(point.id)),
                text=payload.get("text", ""),
                metadata=payload.get("metadata", {}),
            )
            results.append(SearchResult(chunk=chunk, score=point.score))
        return results

    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
    ) -> List[SearchResult]:
        response = await self.client.query_points(
            collection_name=collection_name,
            query=query_vector,
            using="dense",
            limit=limit,
            with_payload=True,
        )
        return self._map_points_to_results(response.points)

    async def search_sparse(
        self,
        collection_name: str,
        sparse_query: SparseVectorSchema,
        limit: int = 5,
    ) -> List[SearchResult]:
        response = await self.client.query_points(
            collection_name=collection_name,
            query=SparseVector(
                indices=sparse_query.indices,
                values=sparse_query.values,
            ),
            using="sparse",
            limit=limit,
            with_payload=True,
        )
        return self._map_points_to_results(response.points)

    async def delete_chunks_by_source(self, collection_name: str, source: str) -> None:
        if not await self.client.collection_exists(collection_name):
            return
        await self.client.delete(
            collection_name=collection_name,
            points_selector=FilterSelector(
                filter=Filter(
                    must=[FieldCondition(key="metadata.source", match=MatchValue(value=source))]
                )
            ),
        )

    async def upsert_chunks(
        self,
        collection_name: str,
        chunks: List[DocumentChunk],
        vectors: List[List[float]],
        sparse_vectors: Optional[List[SparseVectorSchema]] = None,
    ) -> bool:
        if len(chunks) != len(vectors):
            raise ValueError("The number of chunks must match the number of dense vectors.")
        if sparse_vectors is not None and len(sparse_vectors) != len(chunks):
            raise ValueError("The number of sparse vectors must match the number of chunks.")

        if sparse_vectors is not None:
            points = [
                PointStruct(
                    id=chunk.id,
                    vector={
                        "dense": dense_vec,
                        "sparse": SparseVector(
                            indices=sp_vec.indices,
                            values=sp_vec.values,
                        ),
                    },
                    payload={"text": chunk.text, "metadata": chunk.metadata},
                )
                for chunk, dense_vec, sp_vec in zip(chunks, vectors, sparse_vectors)
            ]
        else:
            points = [
                PointStruct(
                    id=chunk.id,
                    vector=dense_vec,
                    payload={"text": chunk.text, "metadata": chunk.metadata},
                )
                for chunk, dense_vec in zip(chunks, vectors)
            ]

        await self.client.upsert(collection_name=collection_name, points=points)
        return True

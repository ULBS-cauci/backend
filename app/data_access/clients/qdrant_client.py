from typing import List
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Optional, PointStruct, VectorParams, Distance

from data_access.interfaces.vector_db import VectorDBClient
from schemas.vector_schemas import DocumentChunk, SearchResult

class QdrantClient(VectorDBClient):
    """
    Concrete implementation of the VectorDBClient using Qdrant.
    """
    def __init__(self, host: str, port: int, api_key: Optional[str] = None):
        # The SDK explicitly uses the host and port provided
        self.client = AsyncQdrantClient(host=host, port=port, api_key=api_key)

    async def create_collection(self, collection_name: str, vector_size: int) -> bool:
        if await self.client.collection_exists(collection_name=collection_name):
            return False 
            
        await self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=vector_size, 
                distance=Distance.COSINE 
            )
        )
        return True

    async def delete_collection(self, collection_name: str) -> bool:
        if not await self.client.collection_exists(collection_name=collection_name):
            return False
            
        await self.client.delete_collection(collection_name=collection_name)
        return True

    async def search(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[SearchResult]:
        results = await self.client.search(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        
        domain_results = []
        for point in results:
            payload = point.payload or {}
            chunk = DocumentChunk(
                id=str(point.id),
                text=payload.get("text", ""),
                metadata=payload.get("metadata", {})
            )
            domain_results.append(SearchResult(chunk=chunk, score=point.score))
            
        return domain_results

    async def upsert_chunks(self, collection_name: str, chunks: List[DocumentChunk], vectors: List[List[float]]) -> bool:
        if len(chunks) != len(vectors):
            raise ValueError("The number of chunks must match the number of vectors.")

        points = [
            PointStruct(
                id=chunk.id,
                vector=vector,
                payload={"text": chunk.text, "metadata": chunk.metadata}
            )
            for chunk, vector in zip(chunks, vectors)
        ]
        
        await self.client.upsert(
            collection_name=collection_name,
            points=points
        )
        return True
from abc import ABC, abstractmethod
from typing import List, Optional
from app.schemas.vector_schemas import DocumentChunk, SearchResult, SparseVectorSchema

class VectorDBInterface(ABC):
    """
    Abstract Base Class defining the contract for any Vector Database
    used in the AI Tutor application.
    """
    
    @abstractmethod
    async def create_collection(self, collection_name: str, vector_size: int, sparse: bool = False) -> bool:
        """
        Creates a new collection/index in the vector database.

        Args:
            collection_name (str): The unique identifier for the collection (e.g., 'biology_101').
            vector_size (int): The dimensionality of the embeddings (e.g., 768 for open-source, 1536 for OpenAI).
            sparse (bool): When True, creates named vector slots for both dense and BM25 sparse vectors.
                           Defaults to False (flat unnamed dense vector, legacy behaviour).

        Returns:
            bool: True if the collection was successfully created, False if it already existed.

        Note:
            Implementations should default to using Cosine Similarity as the distance metric
            unless otherwise specified.
        """
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> bool:
        """
        Permanently deletes a collection and all its underlying data.
        
        Args:
            collection_name (str): The name of the collection to drop.
            
        Returns:
            bool: True if successfully deleted, False if the collection did not exist.
            
        Warning:
            This is a destructive action and cannot be undone. Implementations must 
            ensure this drops both the vectors and their associated payload/metadata.
        """
        pass

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Performs a dense (semantic) vector search.

        Args:
            collection_name (str): The name of the collection to search against.
            query_vector (List[float]): Dense embedding of the user's query.
            limit (int): Maximum number of results to return. Defaults to 5.

        Returns:
            List[SearchResult]: Results sorted from highest to lowest cosine similarity.
        """
        pass

    @abstractmethod
    async def search_sparse(
        self,
        collection_name: str,
        sparse_query: SparseVectorSchema,
        limit: int = 5,
    ) -> List[SearchResult]:
        """
        Performs a sparse (BM25 keyword) vector search.

        Args:
            collection_name (str): The name of the collection to search against.
            sparse_query (SparseVectorSchema): BM25 sparse vector for the query.
            limit (int): Maximum number of results to return. Defaults to 5.

        Returns:
            List[SearchResult]: Results sorted from highest to lowest BM25 score.
        """
        pass

    @abstractmethod
    async def upsert_chunks(
        self,
        collection_name: str,
        chunks: List[DocumentChunk],
        vectors: List[List[float]],
        sparse_vectors: Optional[List[SparseVectorSchema]] = None,
    ) -> bool:
        """
        Uploads document chunks and their corresponding embeddings into the database.

        When sparse_vectors is provided, implementations must store both dense and sparse vectors
        as named vector slots ("dense" / "sparse"). When omitted, stores a flat dense vector (legacy).

        Args:
            collection_name (str): The destination collection.
            chunks (List[DocumentChunk]): Domain models containing the raw text, ID, and metadata.
            vectors (List[List[float]]): Dense embeddings corresponding to each chunk.
            sparse_vectors (List[SparseVectorSchema], optional): BM25 sparse vectors for each chunk.

        Returns:
            bool: True if the batch upload was fully successful.

        Raises:
            ValueError: If the length of chunks, vectors, or sparse_vectors do not all match.

        Note:
            This is an "upsert" operation. If a chunk ID already exists it is overwritten.
        """
        pass
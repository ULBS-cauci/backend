from abc import ABC, abstractmethod
from typing import List
from schemas.vector_schemas import DocumentChunk, SearchResult

class VectorDBClient(ABC):
    """
    Abstract Base Class defining the contract for any Vector Database
    used in the AI Tutor application.
    """
    
    @abstractmethod
    async def create_collection(self, collection_name: str, vector_size: int) -> bool:
        """
        Creates a new collection/index in the vector database.
        
        Args:
            collection_name (str): The unique identifier for the collection (e.g., 'biology_101').
            vector_size (int): The dimensionality of the embeddings (e.g., 768 for open-source, 1536 for OpenAI).
            
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
    async def search(self, collection_name: str, query_vector: List[float], limit: int = 5) -> List[SearchResult]:
        """
        Performs a semantic vector search to find the most relevant document chunks.
        
        Args:
            collection_name (str): The name of the collection to search against.
            query_vector (List[float]): The embedded numerical representation of the user's query.
            limit (int, optional): The maximum number of results to return. Defaults to 5.
            
        Returns:
            List[SearchResult]: A list of domain models containing the chunk data and its relevance 
            score, strictly sorted from highest relevance to lowest relevance.
        """
        pass

    @abstractmethod
    async def upsert_chunks(self, collection_name: str, chunks: List[DocumentChunk], vectors: List[List[float]]) -> bool:
        """
        Uploads document chunks and their corresponding embeddings into the database.
        
        Args:
            collection_name (str): The destination collection.
            chunks (List[DocumentChunk]): Domain models containing the raw text, ID, and metadata.
            vectors (List[List[float]]): The embeddings corresponding to each chunk.
            
        Returns:
            bool: True if the batch upload was fully successful.
            
        Raises:
            ValueError: Implementations should raise an error if the length of `chunks` 
            does not perfectly match the length of `vectors`.
            
        Note:
            This is an "upsert" operation. If a chunk ID already exists in the database, 
            it should overwrite the existing vector and payload.
        """
        pass
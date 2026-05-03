from abc import ABC, abstractmethod
from typing import TypeVar, Type, Any, Optional, Sequence
from sqlmodel import SQLModel

T = TypeVar("T", bound=SQLModel)

class IRelationalDB(ABC):
    """
    Abstract Base Class defining the contract for generic relational database operations.
    It relies entirely on SQLModel objects, keeping business logic out of the data access layer.
    """

    @abstractmethod
    async def add(self, record: T) -> T:
        """
        Inserts a new SQLModel record into the database.
        
        Args:
            record (T): The SQLModel instance to save.
            
        Returns:
            T: The saved instance, updated with its generated primary key.
        """
        pass

    @abstractmethod
    async def get(self, model_class: Type[T], record_id: Any) -> Optional[T]:
        """
        Retrieves a single record by its primary key.
        
        Args:
            model_class (Type[T]): The SQLModel class (e.g., User, ChatSession).
            record_id (Any): The primary key to search for.
            
        Returns:
            Optional[T]: The record if found, otherwise None.
        """
        pass

    @abstractmethod
    async def execute(self, statement: Any) -> Any:
        """
        Executes a compiled SQLModel select/update/delete statement.
        This allows the Service layer to build complex queries (the business logic)
        while the client simply executes them.
        
        Args:
            statement (Any): The SQLModel statement.
            
        Returns:
            Any: The raw execution result.
        """
        pass
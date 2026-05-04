from sqlmodel.ext.asyncio.session import AsyncSession
from typing import Type, Any, Optional
from app.data_access.interfaces.relational_db import IRelationalDB, T

class PostgresClient(IRelationalDB):
    """
    Concrete implementation of the RelationalDB interface using PostgreSQL (via asyncpg).
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, record: T) -> T:
        """
        Adds a new record to the session and flushes it to the database to populate 
        auto-generated fields (e.g., primary keys).
        
        Note: This method does NOT commit the transaction. The caller (or the 
        dependency injection session generator) is responsible for calling commit().
        """
        self.session.add(record)
        await self.session.flush() 
        await self.session.refresh(record)
        return record

    async def get(self, model_class: Type[T], record_id: Any) -> Optional[T]:
        return await self.session.get(model_class, record_id)

    async def execute(self, statement: Any) -> Any:
        return await self.session.execute(statement)
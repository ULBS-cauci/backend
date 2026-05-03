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
        self.session.add(record)
        # Flush trimite query-ul catre DB pentru a genera ID-ul, 
        # dar pastreaza tranzactia deschisa pentru siguranta
        await self.session.flush() 
        return record

    async def get(self, model_class: Type[T], record_id: Any) -> Optional[T]:
        return await self.session.get(model_class, record_id)

    async def execute(self, statement: Any) -> Any:
        return await self.session.execute(statement)
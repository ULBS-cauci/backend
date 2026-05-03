from app.core.config import Settings
from app.data_access.clients.qdrant_client import QdrantClient
from app.data_access.interfaces.vector_db import VectorDBInterface

setting = Settings()

_qdrant_vector_db_client = QdrantClient(
    endpoint=setting.VECTOR_DB_ENDPOINT,
    api_key=setting.VECTOR_DB_SERVICE_API_KEY,
)

def get_vector_db_client() -> VectorDBInterface:
    if setting.VECTOR_DB_TYPE == "qdrant":
        return _qdrant_vector_db_client
    else:
        raise ValueError(f"Unsupported Vector Database type: {setting.VECTOR_DB_TYPE}")

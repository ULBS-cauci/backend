from app.core.config import Settings
from backend.app.data_access.clients.qdrant_client import QdrantClient
from backend.app.data_access.interfaces.vector_db import VectorDBClient

setting = Settings()

_qdrant_vector_db_client = QdrantClient(
    host=setting.QDRANT_HOST,
    port=setting.QDRANT_PORT,
    api_key=setting.QDRANT_SERVICE_API_KEY
)

def get_vector_db_client() -> VectorDBClient:
    if setting.VECTOR_DB_TYPE == "qdrant":
        return _qdrant_vector_db_client
    else:
        raise ValueError(f"Unsupported Vector Database type: {setting.VECTOR_DB_TYPE}")

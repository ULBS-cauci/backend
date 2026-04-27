from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # These names must exactly match your .env file
    VECTOR_DB_TYPE: str
    QDRANT_HOST: str
    QDRANT_PORT: int
    QDRANT_SERVICE_API_KEY: Optional[str] = None

    # This tells Pydantic to look for the .env file in your root directory
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
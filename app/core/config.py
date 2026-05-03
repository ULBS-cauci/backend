from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    # Vector DB
    VECTOR_DB_TYPE: str
    VECTOR_DB_ENDPOINT: str
    VECTOR_DB_SERVICE_API_KEY: Optional[str] = None

    # Object Storage
    OBJECT_STORAGE_TYPE: str
    OBJECT_STORAGE_ENDPOINT: str
    OBJECT_STORAGE_ACCESS_KEY: str
    OBJECT_STORAGE_SECRET_KEY: str
    OBJECT_STORAGE_USE_SSL: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

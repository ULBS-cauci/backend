"""
Interface-level bridge for non-FastAPI consumers (e.g. the ARQ worker).

All functions return abstract interfaces, not concrete clients.
To swap a provider, edit dependencies.py only — nothing here needs to change.
"""
from sqlalchemy.ext.asyncio import AsyncEngine

from app.data_access.interfaces.embedding import EmbeddingInterface
from app.data_access.interfaces.object_storage import ObjectStorageInterface
from app.data_access.interfaces.reranker import RerankerInterface
from app.data_access.interfaces.sparse_encoder import SparseEncoderInterface
from app.data_access.interfaces.text_splitter import TextSplitterInterface
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.api.dependencies import (
    select_embedding_client,
    select_object_storage_client,
    select_reranker,
    select_sparse_encoder,
    select_text_splitter,
    select_vector_db_client,
    get_worker_db_engine,
)


def get_worker_vector_db() -> VectorDBInterface:
    return select_vector_db_client()


def get_worker_embed() -> EmbeddingInterface:
    return select_embedding_client()


def get_worker_object_storage() -> ObjectStorageInterface:
    return select_object_storage_client()


def get_worker_sparse_encoder() -> SparseEncoderInterface:
    return select_sparse_encoder()


def get_worker_text_splitter() -> TextSplitterInterface:
    return select_text_splitter()


def get_worker_reranker() -> RerankerInterface:
    return select_reranker()


def get_worker_engine() -> AsyncEngine:
    return get_worker_db_engine()

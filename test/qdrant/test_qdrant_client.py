"""
Integration test for QdrantClient — runs against a live Qdrant instance.
Run from the backend/ directory so that .env is found automatically:

    cd backend
    .venv/bin/python test/qdrant/test_qdrant_client.py
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

_backend = os.path.join(os.path.dirname(__file__), "..", "..")
load_dotenv(dotenv_path=os.path.join(_backend, ".env"))
sys.path.insert(0, os.path.abspath(_backend))

import uuid
from app.api.dependencies import get_vector_db_client, get_app_settings
from app.core.config import QdrantSettings
from app.data_access.interfaces.vector_db import VectorDBInterface
from app.schemas.vector_schemas import DocumentChunk

COLLECTION = "test-collection"
VECTOR_SIZE = 4

ID_BIOLOGY_1 = uuid.UUID("a0000000-0000-0000-0000-000000000001")
ID_BIOLOGY_2 = uuid.UUID("a0000000-0000-0000-0000-000000000002")
ID_PHYSICS_1 = uuid.UUID("a0000000-0000-0000-0000-000000000003")

CHUNKS = [
    DocumentChunk(id=ID_BIOLOGY_1, text="The mitochondria is the powerhouse of the cell.", metadata={"source": "biology"}),
    DocumentChunk(id=ID_BIOLOGY_2, text="Photosynthesis converts light into chemical energy.", metadata={"source": "biology"}),
    DocumentChunk(id=ID_PHYSICS_1, text="Newton's second law: F = ma.", metadata={"source": "physics"}),
]

VECTORS = [
    [0.9, 0.1, 0.0, 0.0],
    [0.8, 0.2, 0.0, 0.1],
    [0.0, 0.0, 0.9, 0.1],
]


def ok(label: str) -> None:
    print(f"  [PASS] {label}")


def fail(label: str, err: Exception) -> None:
    print(f"  [FAIL] {label}: {err}")


async def run() -> None:
    client: VectorDBInterface = get_vector_db_client(get_app_settings())
    settings = QdrantSettings()
    print(f"\nTarget     : {settings.QDRANT_ENDPOINT}")
    print(f"Collection : {COLLECTION}\n")

    # ── create_collection ─────────────────────────────────────────────────────
    try:
        created = await client.create_collection(COLLECTION, VECTOR_SIZE)
        assert created is True, f"expected True (new collection), got {created}"
        ok("create_collection — new collection returns True")
    except Exception as e:
        fail("create_collection — new collection", e)

    try:
        created_again = await client.create_collection(COLLECTION, VECTOR_SIZE)
        assert created_again is False, f"expected False (already exists), got {created_again}"
        ok("create_collection — existing collection returns False")
    except Exception as e:
        fail("create_collection — existing collection", e)

    # ── upsert_chunks ──────────────────────────────────────────────────────────
    try:
        result = await client.upsert_chunks(COLLECTION, CHUNKS, VECTORS)
        assert result is True
        ok("upsert_chunks — batch upload returns True")
    except Exception as e:
        fail("upsert_chunks — batch upload", e)

    try:
        await client.upsert_chunks(COLLECTION, CHUNKS, VECTORS[:2])
        fail("upsert_chunks — mismatched lengths should raise", AssertionError("no exception raised"))
    except ValueError:
        ok("upsert_chunks — mismatched chunk/vector lengths raises ValueError")
    except Exception as e:
        fail("upsert_chunks — mismatched lengths wrong exception", e)

    # ── search ─────────────────────────────────────────────────────────────────
    try:
        biology_query = [0.85, 0.15, 0.0, 0.0]
        results = await client.search(COLLECTION, biology_query, limit=2)
        assert len(results) == 2, f"expected 2 results, got {len(results)}"
        assert results[0].score >= results[1].score, "results not sorted by score descending"
        assert all(r.chunk.text for r in results), "result chunks missing text"
        ok(f"search — returns {len(results)} results sorted by score")
    except Exception as e:
        fail("search — basic query", e)

    try:
        physics_query = [0.0, 0.0, 0.95, 0.05]
        results = await client.search(COLLECTION, physics_query, limit=1)
        assert len(results) == 1
        assert results[0].chunk.id == ID_PHYSICS_1, f"expected chunk id '{ID_PHYSICS_1}', got '{results[0].chunk.id}'"
        ok("search — physics query returns the physics chunk as top result")
    except Exception as e:
        fail("search — physics query top result", e)

    try:
        results = await client.search(COLLECTION, [0.85, 0.15, 0.0, 0.0], limit=5)
        assert len(results) <= 3, f"limit > total points should return at most 3, got {len(results)}"
        ok(f"search — limit larger than total points returns {len(results)} result(s)")
    except Exception as e:
        fail("search — limit larger than total points", e)

    # ── upsert_chunks (overwrite existing) ────────────────────────────────────
    try:
        updated_chunk = [DocumentChunk(id=ID_BIOLOGY_1, text="Updated: mitochondria text.", metadata={"source": "biology_v2"})]
        updated_vector = [[0.88, 0.12, 0.0, 0.0]]
        result = await client.upsert_chunks(COLLECTION, updated_chunk, updated_vector)
        assert result is True
        results = await client.search(COLLECTION, [0.88, 0.12, 0.0, 0.0], limit=1)
        assert results[0].chunk.text == "Updated: mitochondria text."
        ok("upsert_chunks — re-upserting existing id overwrites payload")
    except Exception as e:
        fail("upsert_chunks — overwrite existing id", e)

    # ── delete_collection ──────────────────────────────────────────────────────
    try:
        deleted = await client.delete_collection(COLLECTION)
        assert deleted is True
        ok("delete_collection — existing collection returns True")
    except Exception as e:
        fail("delete_collection — existing collection", e)

    try:
        deleted_again = await client.delete_collection(COLLECTION)
        assert deleted_again is False
        ok("delete_collection — non-existent collection returns False")
    except Exception as e:
        fail("delete_collection — non-existent collection", e)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(run())

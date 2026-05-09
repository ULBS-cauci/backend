"""
Integration test for MinIOClient — runs against a live MinIO instance.
Run from the backend/ directory so that .env is found automatically:

    cd backend
    .venv/bin/python test/minio/test_minio_client.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.api.dependencies import get_object_storage_client, get_app_settings, get_minio_settings
from app.data_access.interfaces.object_storage import ObjectStorageInterface

BUCKET = "test-bucket"
KEY = "folder/hello.txt"
CONTENT = b"Hello from MinIO integration test!"


def ok(label: str) -> None:
    print(f"  [PASS] {label}")


def fail(label: str, err: Exception) -> None:
    print(f"  [FAIL] {label}: {err}")


async def run() -> None:
    client: ObjectStorageInterface = get_object_storage_client(get_app_settings())
    print(f"\nTarget  : {get_minio_settings().MINIO_ENDPOINT}")
    print(f"Bucket  : {BUCKET}\n")

    # ── create_bucket ─────────────────────────────────────────────────────────
    try:
        created = await client.create_bucket(BUCKET)
        assert created is True, f"expected True (new bucket), got {created}"
        ok("create_bucket — new bucket returns True")
    except Exception as e:
        fail("create_bucket — new bucket", e)

    try:
        created_again = await client.create_bucket(BUCKET)
        assert created_again is False, f"expected False (already exists), got {created_again}"
        ok("create_bucket — existing bucket returns False")
    except Exception as e:
        fail("create_bucket — existing bucket", e)

    # ── upload_file ────────────────────────────────────────────────────────────
    try:
        result = await client.upload_file(BUCKET, KEY, CONTENT, content_type="text/plain")
        assert result is True
        ok("upload_file")
    except Exception as e:
        fail("upload_file", e)

    # ── file_exists ────────────────────────────────────────────────────────────
    try:
        exists = await client.file_exists(BUCKET, KEY)
        assert exists is True
        ok("file_exists — uploaded file found")
    except Exception as e:
        fail("file_exists — uploaded file", e)

    try:
        missing = await client.file_exists(BUCKET, "does/not/exist.txt")
        assert missing is False
        ok("file_exists — missing file returns False")
    except Exception as e:
        fail("file_exists — missing file", e)

    # ── list_files ─────────────────────────────────────────────────────────────
    try:
        all_keys = await client.list_files(BUCKET)
        assert KEY in all_keys, f"{KEY} not in {all_keys}"
        ok(f"list_files — found {len(all_keys)} object(s)")
    except Exception as e:
        fail("list_files", e)

    try:
        prefixed = await client.list_files(BUCKET, prefix="folder/")
        assert KEY in prefixed
        ok("list_files — prefix filter works")
    except Exception as e:
        fail("list_files — prefix filter", e)

    try:
        empty = await client.list_files(BUCKET, prefix="nonexistent/")
        assert empty == []
        ok("list_files — non-matching prefix returns empty list")
    except Exception as e:
        fail("list_files — non-matching prefix", e)

    # ── download_file ──────────────────────────────────────────────────────────
    try:
        data = await client.download_file(BUCKET, KEY)
        assert data == CONTENT, f"content mismatch: {data!r}"
        ok("download_file — content matches")
    except Exception as e:
        fail("download_file", e)

    try:
        await client.download_file(BUCKET, "does/not/exist.txt")
        fail("download_file — missing key should raise", AssertionError("no exception raised"))
    except FileNotFoundError:
        ok("download_file — missing key raises FileNotFoundError")
    except Exception as e:
        fail("download_file — missing key wrong exception", e)

    # ── delete_file ────────────────────────────────────────────────────────────
    try:
        deleted = await client.delete_file(BUCKET, KEY)
        assert deleted is True
        ok("delete_file — existing file returns True")
    except Exception as e:
        fail("delete_file — existing file", e)

    try:
        deleted_again = await client.delete_file(BUCKET, KEY)
        assert deleted_again is False
        ok("delete_file — already-deleted file returns False")
    except Exception as e:
        fail("delete_file — already-deleted file", e)

    try:
        gone = await client.file_exists(BUCKET, KEY)
        assert gone is False
        ok("file_exists — deleted file no longer found")
    except Exception as e:
        fail("file_exists — after delete", e)

    # ── delete_bucket ──────────────────────────────────────────────────────────
    try:
        bucket_deleted = await client.delete_bucket(BUCKET, force=True)
        assert bucket_deleted is True
        ok("delete_bucket — existing bucket returns True")
    except Exception as e:
        fail("delete_bucket — existing bucket", e)

    try:
        bucket_missing = await client.delete_bucket(BUCKET)
        assert bucket_missing is False
        ok("delete_bucket — non-existent bucket returns False")
    except Exception as e:
        fail("delete_bucket — non-existent bucket", e)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(run())

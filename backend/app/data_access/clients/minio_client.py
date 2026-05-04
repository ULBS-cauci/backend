from typing import List, Optional

import aioboto3
from botocore.exceptions import ClientError

from app.data_access.interfaces.object_storage import ObjectStorageInterface


class MinIOClient(ObjectStorageInterface):
    """
    Concrete implementation of ObjectStorageInterface backed by MinIO
    via the aioboto3 S3-compatible async SDK.

    A single aioboto3.Session is created at __init__ time and reused for every
    operation. Each public method opens its own short-lived async context manager
    around the S3 resource — the aioboto3 pattern for long-running services.
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        use_ssl: bool = True,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._use_ssl = use_ssl
        self._session = aioboto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def _s3_resource(self):
        """High-level object API — used for upload, download, delete."""
        return self._session.resource(
            "s3",
            endpoint_url=self._endpoint_url,
            use_ssl=self._use_ssl,
            region_name="us-east-1",
        )

    def _s3_client(self):
        """Low-level client API — used for head_object, presigned URLs, paginators."""
        return self._session.client(
            "s3",
            endpoint_url=self._endpoint_url,
            use_ssl=self._use_ssl,
            region_name="us-east-1",
        )

    async def create_bucket(self, bucket_name: str) -> bool:
        async with self._s3_client() as client:
            try:
                await client.head_bucket(Bucket=bucket_name)
                return False
            except ClientError as exc:
                if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                    raise
            await client.create_bucket(Bucket=bucket_name)
            return True

    async def upload_file(
        self,
        bucket_name: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> bool:
        async with self._s3_resource() as s3:
            obj = await s3.Object(bucket_name, object_key)
            await obj.put(Body=data, ContentType=content_type)
        return True

    async def download_file(self, bucket_name: str, object_key: str) -> bytes:
        async with self._s3_resource() as s3:
            try:
                obj = await s3.Object(bucket_name, object_key)
                response = await obj.get()
                return await response["Body"].read()
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    raise FileNotFoundError(
                        f"'{object_key}' not found in bucket '{bucket_name}'"
                    ) from exc
                raise

    async def delete_file(self, bucket_name: str, object_key: str) -> bool:
        if not await self.file_exists(bucket_name, object_key):
            return False
        async with self._s3_resource() as s3:
            obj = await s3.Object(bucket_name, object_key)
            await obj.delete()
        return True

    async def file_exists(self, bucket_name: str, object_key: str) -> bool:
        async with self._s3_client() as client:
            try:
                await client.head_object(Bucket=bucket_name, Key=object_key)
                return True
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                    return False
                raise

    async def list_files(
        self,
        bucket_name: str,
        prefix: Optional[str] = None,
    ) -> List[str]:
        keys: List[str] = []
        kwargs = {"Bucket": bucket_name}
        if prefix:
            kwargs["Prefix"] = prefix
        async with self._s3_client() as client:
            paginator = client.get_paginator("list_objects_v2")
            async for page in paginator.paginate(**kwargs):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
        return keys

    async def delete_bucket(self, bucket_name: str, force: bool = True) -> bool:
        async with self._s3_client() as client:
            try:
                await client.head_bucket(Bucket=bucket_name)
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                    return False
                raise
            if force:
                for key in await self.list_files(bucket_name):
                    await self.delete_file(bucket_name, key)
            await client.delete_bucket(Bucket=bucket_name)
            return True

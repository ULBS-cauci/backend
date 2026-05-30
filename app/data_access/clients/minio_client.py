from contextlib import AsyncExitStack
from typing import List, Optional

import aioboto3
from botocore.exceptions import ClientError

from app.data_access.interfaces.object_storage import ObjectStorageInterface


class MinIOClient(ObjectStorageInterface):
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
        self._client = None
        self._resource = None
        self._exit_stack: Optional[AsyncExitStack] = None

    def _require_connected(self) -> None:
        if self._client is None or self._resource is None:
            raise RuntimeError("MinIOClient is not connected. Call connect() first.")

    async def connect(self) -> None:
        stack = AsyncExitStack()
        try:
            self._client = await stack.enter_async_context(
                self._session.client(
                    "s3",
                    endpoint_url=self._endpoint_url,
                    use_ssl=self._use_ssl,
                    region_name="us-east-1",
                )
            )
            self._resource = await stack.enter_async_context(
                self._session.resource(
                    "s3",
                    endpoint_url=self._endpoint_url,
                    use_ssl=self._use_ssl,
                    region_name="us-east-1",
                )
            )
        except Exception:
            await stack.aclose()
            raise
        self._exit_stack = stack

    async def close(self) -> None:
        stack = self._exit_stack
        if stack is None:
            return
        self._exit_stack = None
        self._client = None
        self._resource = None
        await stack.aclose()

    async def create_bucket(self, bucket_name: str) -> bool:
        self._require_connected()
        try:
            await self._client.head_bucket(Bucket=bucket_name)
            return False
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in ("404", "NoSuchBucket"):
                raise
        try:
            await self._client.create_bucket(Bucket=bucket_name)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in (
                "BucketAlreadyOwnedByYou",
                "BucketAlreadyExists",
            ):
                return False
            raise
        return True

    async def upload_file(
        self,
        bucket_name: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> bool:
        self._require_connected()
        obj = await self._resource.Object(bucket_name, object_key)
        await obj.put(Body=data, ContentType=content_type)
        return True

    async def download_file(self, bucket_name: str, object_key: str) -> bytes:
        self._require_connected()
        try:
            obj = await self._resource.Object(bucket_name, object_key)
            response = await obj.get()
            return await response["Body"].read()
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                raise FileNotFoundError(
                    f"'{object_key}' not found in bucket '{bucket_name}'"
                ) from exc
            raise

    async def delete_file(self, bucket_name: str, object_key: str) -> bool:
        self._require_connected()
        try:
            await self._client.head_object(Bucket=bucket_name, Key=object_key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
                return False
            raise
        obj = await self._resource.Object(bucket_name, object_key)
        await obj.delete()
        return True

    async def file_exists(self, bucket_name: str, object_key: str) -> bool:
        self._require_connected()
        try:
            await self._client.head_object(Bucket=bucket_name, Key=object_key)
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
        self._require_connected()
        keys: List[str] = []
        kwargs = {"Bucket": bucket_name}
        if prefix:
            kwargs["Prefix"] = prefix
        paginator = self._client.get_paginator("list_objects_v2")
        async for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])
        return keys

    async def delete_bucket(self, bucket_name: str, force: bool = True) -> bool:
        self._require_connected()
        try:
            await self._client.head_bucket(Bucket=bucket_name)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                return False
            raise
        if force:
            for key in await self.list_files(bucket_name):
                await self.delete_file(bucket_name, key)
        await self._client.delete_bucket(Bucket=bucket_name)
        return True

    async def generate_presigned_url(
        self,
        bucket_name: str,
        object_key: str,
        expiry_seconds: int = 3600,
    ) -> str:
        self._require_connected()
        return await self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket_name, "Key": object_key},
            ExpiresIn=expiry_seconds,
        )

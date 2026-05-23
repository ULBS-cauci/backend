from abc import ABC, abstractmethod
from typing import List, Optional


class ObjectStorageInterface(ABC):
    """
    Abstract Base Class defining the contract for any object/blob storage
    backend (MinIO, AWS S3, GCS, Azure Blob, etc.).

    All methods are async. Implementations must never block the event loop.
    """

    @abstractmethod
    async def create_bucket(self, bucket_name: str) -> bool:
        """
        Ensures the bucket exists, creating it if necessary.

        Returns:
            True  if the bucket was newly created.
            False if the bucket already existed.
        """
        pass

    @abstractmethod
    async def delete_bucket(self, bucket_name: str, force: bool = True) -> bool:
        """
        Deletes a bucket.

        Args:
            force: If True, deletes all objects inside the bucket before removing it.
                   If False and the bucket is non-empty, raises an error.

        Returns:
            True  if the bucket was deleted.
            False if the bucket did not exist.
        """
        pass

    @abstractmethod
    async def upload_file(
        self,
        bucket_name: str,
        object_key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> bool:
        """
        Uploads raw bytes under the given object key.

        Args:
            object_key:   Full path/name inside the bucket (e.g. "course_123/slides.pdf").
            content_type: MIME type stored as object metadata.

        Returns:
            True on success.

        Raises:
            IOError: If the upload fails.
        """
        pass

    @abstractmethod
    async def download_file(self, bucket_name: str, object_key: str) -> bytes:
        """
        Downloads the object and returns its raw bytes.

        Raises:
            FileNotFoundError: If the object does not exist.
        """
        pass

    @abstractmethod
    async def delete_file(self, bucket_name: str, object_key: str) -> bool:
        """
        Permanently deletes the object.

        Returns:
            True  if the object was deleted.
            False if the object did not exist.
        """
        pass

    @abstractmethod
    async def file_exists(self, bucket_name: str, object_key: str) -> bool:
        """
        Checks whether an object exists using a HEAD request — never downloads the body.
        """
        pass

    @abstractmethod
    async def generate_presigned_url(
        self,
        bucket_name: str,
        object_key: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """
        Generates a time-limited pre-signed URL for direct browser access to an object.

        Args:
            expiry_seconds: How long the URL remains valid. Defaults to 1 hour.

        Returns:
            A URL string the browser can use to fetch the object directly.
        """
        pass

    @abstractmethod
    async def list_files(
        self,
        bucket_name: str,
        prefix: Optional[str] = None,
    ) -> List[str]:
        """
        Lists object keys inside a bucket, paginated internally.

        Args:
            prefix: Only return keys that start with this string
                    (e.g. "course_123/" to scope to one course).

        Returns:
            List of matching object key strings.
        """
        pass

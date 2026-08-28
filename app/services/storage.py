"""Storage service for uploading generated image assets to MinIO."""

import asyncio
import io
import json
from typing import Optional
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import logger


class StorageService:
    """Service for uploading generated images to MinIO object storage."""

    def __init__(self):
        """Initialize the storage service with MinIO client."""
        self._client: Optional[Minio] = None
        self._bucket_verified: bool = False

    def _get_client(self) -> Minio:
        """Lazy-initialize MinIO client."""
        if self._client is not None:
            return self._client

        try:
            endpoint = settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", "").rstrip("/")
            self._client = Minio(
                endpoint,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE,
            )
            return self._client
        except Exception as e:
            logger.exception("minio_client_init_failed", error=str(e))
            raise RuntimeError("MinIO client initialization failed") from e

    def _ensure_bucket(self, client: Minio, bucket_name: str) -> None:
        """Ensure that the target bucket exists and has public read access."""
        if self._bucket_verified:
            return

        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                logger.info("minio_bucket_created", bucket=bucket_name)

                policy = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Principal": {"AWS": ["*"]},
                            "Action": ["s3:GetObject"],
                            "Resource": [f"arn:aws:s3:::{bucket_name}/*"],
                        }
                    ],
                }
                client.set_bucket_policy(bucket_name, json.dumps(policy))
                logger.info("minio_bucket_policy_set", bucket=bucket_name)

            self._bucket_verified = True
        except Exception as e:
            logger.exception("minio_bucket_verification_failed", bucket=bucket_name, error=str(e))
            raise RuntimeError("MinIO bucket verification failed") from e

    def upload_bytes_sync(
        self,
        data: bytes,
        filename: Optional[str] = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw bytes to MinIO and return a public URL."""
        if not filename:
            filename = f"math_{uuid4().hex[:12]}.bin"

        bucket_name = settings.MINIO_BUCKET
        client = self._get_client()

        try:
            self._ensure_bucket(client, bucket_name)
            data_stream = io.BytesIO(data)
            client.put_object(
                bucket_name,
                filename,
                data_stream,
                length=len(data),
                content_type=content_type,
            )

            if settings.MINIO_PUBLIC_URL:
                base_url = settings.MINIO_PUBLIC_URL.rstrip("/")
                url = f"{base_url}/{filename}"
            else:
                protocol = "https" if settings.MINIO_SECURE else "http"
                url = f"{protocol}://{settings.MINIO_ENDPOINT.rstrip('/')}/{bucket_name}/{filename}"

            logger.info(
                "image_uploaded_to_minio",
                filename=filename,
                bucket=bucket_name,
                size_bytes=len(data),
                url=url,
            )
            return url
        except (S3Error, Exception) as e:
            logger.exception("minio_upload_failed", error=str(e), filename=filename)
            raise RuntimeError(f"MinIO upload failed for {filename}") from e

    def upload_image_bytes_sync(
        self,
        image_bytes: bytes,
        filename: Optional[str] = None,
        content_type: str = "image/png",
    ) -> str:
        """Upload raw image bytes to MinIO and return a public image URL."""
        return self.upload_bytes_sync(
            data=image_bytes,
            filename=filename,
            content_type=content_type,
        )

    async def upload_bytes(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Asynchronously upload arbitrary bytes to MinIO."""
        return await asyncio.to_thread(
            self.upload_bytes_sync,
            data=data,
            filename=filename,
            content_type=content_type,
        )

    async def upload_image_bytes(
        self,
        image_bytes: bytes,
        filename: Optional[str] = None,
        content_type: str = "image/png",
    ) -> str:
        """Asynchronously upload raw image bytes to MinIO storage."""
        return await asyncio.to_thread(
            self.upload_bytes_sync,
            data=image_bytes,
            filename=filename,
            content_type=content_type,
        )


storage_service = StorageService()

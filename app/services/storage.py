"""Storage service for uploading and managing image assets in MinIO with local fallback."""

import asyncio
import base64
import io
import json
import os
from pathlib import Path
from typing import Optional
from uuid import uuid4

from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.core.logging import logger


class StorageService:
    """Service for uploading generated images to MinIO object storage with graceful local fallback."""

    def __init__(self):
        """Initialize the storage service with MinIO client."""
        self._client: Optional[Minio] = None
        self._bucket_verified: bool = False
        self._local_fallback_dir: Path = Path(os.path.dirname(os.path.dirname(__file__))) / "static" / "generated"

    def _get_client(self) -> Optional[Minio]:
        """Lazy-initialize MinIO client."""
        if self._client is None:
            try:
                endpoint = settings.MINIO_ENDPOINT.replace("http://", "").replace("https://", "").rstrip("/")
                self._client = Minio(
                    endpoint,
                    access_key=settings.MINIO_ACCESS_KEY,
                    secret_key=settings.MINIO_SECRET_KEY,
                    secure=settings.MINIO_SECURE,
                )
            except Exception as e:
                logger.warning("minio_client_init_failed", error=str(e))
                self._client = None
        return self._client

    def _ensure_bucket(self, client: Minio, bucket_name: str) -> bool:
        """Ensure that the target bucket exists and has public read access."""
        if self._bucket_verified:
            return True

        try:
            if not client.bucket_exists(bucket_name):
                client.make_bucket(bucket_name)
                logger.info("minio_bucket_created", bucket=bucket_name)

                # Set anonymous read-only policy for public image viewing
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
            return True
        except Exception as e:
            logger.warning("minio_bucket_verification_failed", bucket=bucket_name, error=str(e))
            return False

    def upload_image_bytes_sync(
        self,
        image_bytes: bytes,
        filename: Optional[str] = None,
        content_type: str = "image/png",
    ) -> str:
        """Upload raw image bytes to MinIO and return a public image URL.

        Falls back to local static file serving or Base64 data URI if MinIO is unreachable.
        """
        if not filename:
            filename = f"math_{uuid4().hex[:12]}.png"

        bucket_name = settings.MINIO_BUCKET
        client = self._get_client()

        # 1. Try MinIO upload
        if client:
            try:
                self._ensure_bucket(client, bucket_name)
                data_stream = io.BytesIO(image_bytes)
                client.put_object(
                    bucket_name,
                    filename,
                    data_stream,
                    length=len(image_bytes),
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
                    size_bytes=len(image_bytes),
                    url=url,
                )
                return url
            except (S3Error, Exception) as s3_err:
                logger.warning("minio_upload_failed_falling_back", error=str(s3_err), filename=filename)

        # 2. Fallback: Save to local static directory
        try:
            self._local_fallback_dir.mkdir(parents=True, exist_ok=True)
            local_file_path = self._local_fallback_dir / filename
            local_file_path.write_bytes(image_bytes)
            local_url = f"/static/generated/{filename}"
            logger.info("image_saved_locally_fallback", url=local_url, filename=filename)
            return local_url
        except Exception as local_err:
            logger.warning("local_storage_failed_falling_back_to_base64", error=str(local_err))

        # 3. Final Fallback: Base64 data URI
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{content_type};base64,{b64}"

    async def upload_image_bytes(
        self,
        image_bytes: bytes,
        filename: Optional[str] = None,
        content_type: str = "image/png",
    ) -> str:
        """Asynchronously upload raw image bytes to MinIO storage."""
        return await asyncio.to_thread(
            self.upload_image_bytes_sync,
            image_bytes=image_bytes,
            filename=filename,
            content_type=content_type,
        )


storage_service = StorageService()

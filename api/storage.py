from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path, PurePosixPath
from typing import Protocol

from .config import Settings, get_settings


@dataclass(frozen=True)
class StoredObject:
    key: str
    size: int
    content_type: str | None = None


class StorageBackend(Protocol):
    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> StoredObject: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...

    def url(self, key: str, *, expires_in: int = 3600) -> str: ...


def normalize_storage_key(key: str) -> str:
    if not key or "\\" in key:
        raise ValueError("storage key must be a non-empty POSIX path")
    path = PurePosixPath(key)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError("storage key must not be absolute or contain traversal segments")
    return path.as_posix()


class LocalStorage:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        normalized = normalize_storage_key(key)
        target = (self.root / normalized).resolve()
        if self.root not in target.parents:
            raise ValueError("storage key escapes local storage root")
        return target

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> StoredObject:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_name: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
                temporary.write(data)
                temporary_name = temporary.name
            os.replace(temporary_name, target)
        finally:
            if temporary_name and os.path.exists(temporary_name):
                os.unlink(temporary_name)
        return StoredObject(
            key=normalize_storage_key(key), size=len(data), content_type=content_type
        )

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink()
        except FileNotFoundError:
            return

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def url(self, key: str, *, expires_in: int = 3600) -> str:
        del expires_in
        return self._path(key).as_uri()


class S3Storage:
    def __init__(
        self,
        bucket: str,
        *,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str = "us-east-1",
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        client: object | None = None,
    ) -> None:
        if not bucket:
            raise ValueError("S3 bucket is required")
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        if client is None:
            import boto3

            options = {
                "service_name": "s3",
                "endpoint_url": endpoint_url,
                "region_name": region,
            }
            if access_key_id is not None:
                options["aws_access_key_id"] = access_key_id
                options["aws_secret_access_key"] = secret_access_key
            client = boto3.client(**options)
        self.client = client

    def _key(self, key: str) -> str:
        normalized = normalize_storage_key(key)
        return f"{self.prefix}/{normalized}" if self.prefix else normalized

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str | None = None,
    ) -> StoredObject:
        options = {"Bucket": self.bucket, "Key": self._key(key), "Body": data}
        if content_type:
            options["ContentType"] = content_type
        self.client.put_object(**options)
        return StoredObject(
            key=normalize_storage_key(key), size=len(data), content_type=content_type
        )

    def get(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        return response["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 404:
                return False
            raise
        return True

    def url(self, key: str, *, expires_in: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": self._key(key)},
            ExpiresIn=expires_in,
        )


def create_storage(settings: Settings | None = None) -> StorageBackend:
    resolved = settings or get_settings()
    if resolved.storage_backend == "local":
        return LocalStorage(resolved.storage_local_path)
    return S3Storage(
        resolved.storage_s3_bucket or "",
        prefix=resolved.storage_s3_prefix,
        endpoint_url=resolved.storage_s3_endpoint_url,
        region=resolved.storage_s3_region,
        access_key_id=resolved.storage_s3_access_key_id,
        secret_access_key=(
            resolved.storage_s3_secret_access_key.get_secret_value()
            if resolved.storage_s3_secret_access_key
            else None
        ),
    )


@lru_cache
def get_storage() -> StorageBackend:
    """Default dependency; applications override it with their app-scoped backend."""
    return create_storage()

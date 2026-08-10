from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .db_models import AssetStatus, AuditEvent, License, StoredAsset, utc_now
from .licensing import AuthenticatedPrincipal
from .storage import StorageBackend


class StorageQuotaExceeded(RuntimeError):
    pass


class StoredAssetNotFound(LookupError):
    pass


class AssetIntegrityError(RuntimeError):
    pass


@dataclass(frozen=True)
class StorageUsage:
    used_bytes: int
    limit_bytes: int
    object_count: int

    @property
    def remaining_bytes(self) -> int:
        return max(0, self.limit_bytes - self.used_bytes)

    @property
    def usage_percent(self) -> float:
        if self.limit_bytes <= 0:
            return 100.0
        return min(100.0, self.used_bytes / self.limit_bytes * 100.0)


def sanitize_filename(filename: str | None) -> str:
    candidate = (filename or "file").replace("\\", "/").rsplit("/", 1)[-1]
    candidate = "".join(character for character in candidate if ord(character) >= 32)
    candidate = candidate.strip().strip(".")
    return (candidate or "file")[:255]


def normalize_content_type(content_type: str | None) -> str:
    candidate = (content_type or "application/octet-stream").strip().lower()
    if not candidate or any(character in candidate for character in "\r\n"):
        return "application/octet-stream"
    return candidate[:200]


def _usage_query(license_id: uuid.UUID):
    return select(
        func.coalesce(func.sum(StoredAsset.size_bytes), 0),
        func.count(StoredAsset.id),
    ).where(
        StoredAsset.license_id == license_id,
        StoredAsset.status.in_((AssetStatus.PENDING, AssetStatus.READY)),
    )


def _audit(
    session: Session,
    principal: AuthenticatedPrincipal,
    action: str,
    asset: StoredAsset,
) -> None:
    session.add(
        AuditEvent(
            actor_user_id=principal.user_id,
            actor_api_key_id=principal.api_key_id,
            action=action,
            resource_type="stored_asset",
            resource_id=str(asset.id),
            details={"filename": asset.filename, "size_bytes": asset.size_bytes},
        )
    )


def storage_usage(session: Session, principal: AuthenticatedPrincipal) -> StorageUsage:
    used, count = session.execute(_usage_query(principal.license_id)).one()
    return StorageUsage(
        used_bytes=int(used),
        limit_bytes=int(principal.quotas.get("max_storage_bytes", 0)),
        object_count=int(count),
    )


def create_asset(
    session: Session,
    storage: StorageBackend,
    principal: AuthenticatedPrincipal,
    *,
    filename: str | None,
    content_type: str | None,
    data: bytes,
) -> StoredAsset:
    session.scalar(
        select(License).where(License.id == principal.license_id).with_for_update()
    )
    usage = storage_usage(session, principal)
    if len(data) > usage.remaining_bytes:
        raise StorageQuotaExceeded(
            f"storage quota exceeded: {usage.remaining_bytes} bytes remaining"
        )

    asset_id = uuid.uuid4()
    storage_key = f"users/{principal.user_id}/{asset_id}"
    asset = StoredAsset(
        id=asset_id,
        user_id=principal.user_id,
        license_id=principal.license_id,
        storage_key=storage_key,
        filename=sanitize_filename(filename),
        content_type=normalize_content_type(content_type),
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        status=AssetStatus.PENDING,
    )
    session.add(asset)
    session.flush()

    wrote_object = False
    try:
        storage.put(storage_key, data, content_type=asset.content_type)
        wrote_object = True
        asset.status = AssetStatus.READY
        _audit(session, principal, "storage.upload", asset)
        session.commit()
    except Exception:
        session.rollback()
        if wrote_object:
            try:
                storage.delete(storage_key)
            except Exception:
                pass
        raise
    return asset


def list_assets(
    session: Session,
    principal: AuthenticatedPrincipal,
    *,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[StoredAsset], int]:
    condition = (
        StoredAsset.user_id == principal.user_id,
        StoredAsset.status == AssetStatus.READY,
    )
    total = int(
        session.scalar(select(func.count(StoredAsset.id)).where(*condition)) or 0
    )
    assets = list(
        session.scalars(
            select(StoredAsset)
            .where(*condition)
            .order_by(StoredAsset.created_at.desc(), StoredAsset.id.desc())
            .offset(offset)
            .limit(limit)
        )
    )
    return assets, total


def get_asset(
    session: Session,
    principal: AuthenticatedPrincipal,
    asset_id: uuid.UUID,
    *,
    for_update: bool = False,
) -> StoredAsset:
    query = select(StoredAsset).where(
        StoredAsset.id == asset_id,
        StoredAsset.user_id == principal.user_id,
        StoredAsset.status == AssetStatus.READY,
    )
    if for_update:
        query = query.with_for_update()
    asset = session.scalar(query)
    if asset is None:
        raise StoredAssetNotFound(str(asset_id))
    return asset


def delete_asset(
    session: Session,
    storage: StorageBackend,
    principal: AuthenticatedPrincipal,
    asset_id: uuid.UUID,
) -> None:
    asset = get_asset(session, principal, asset_id, for_update=True)
    asset.status = AssetStatus.DELETING
    session.flush()
    try:
        storage.delete(asset.storage_key)
        _audit(session, principal, "storage.delete", asset)
        session.delete(asset)
        session.commit()
    except Exception:
        session.rollback()
        raise


def mark_asset_failed(session: Session, asset: StoredAsset) -> None:
    asset.status = AssetStatus.FAILED
    asset.deleted_at = utc_now()
    session.commit()


def read_asset(
    session: Session,
    storage: StorageBackend,
    principal: AuthenticatedPrincipal,
    asset_id: uuid.UUID,
) -> tuple[StoredAsset, bytes]:
    asset = get_asset(session, principal, asset_id)
    if not storage.exists(asset.storage_key):
        raise StoredAssetNotFound(str(asset_id))
    data = storage.get(asset.storage_key)
    if len(data) != asset.size_bytes or hashlib.sha256(data).hexdigest() != asset.sha256:
        raise AssetIntegrityError(str(asset_id))
    _audit(session, principal, "storage.download", asset)
    session.commit()
    return asset, data


def reconcile_assets(
    session: Session,
    storage: StorageBackend,
    *,
    pending_max_age_seconds: int = 3600,
) -> dict[str, int]:
    cutoff = utc_now() - timedelta(seconds=pending_max_age_seconds)
    records = list(session.scalars(select(StoredAsset)))
    known_keys = {record.storage_key for record in records}
    repaired = failed = orphans = 0
    for asset in records:
        exists = storage.exists(asset.storage_key)
        if asset.status == AssetStatus.PENDING and asset.created_at <= cutoff:
            if exists:
                data = storage.get(asset.storage_key)
                valid = len(data) == asset.size_bytes and hashlib.sha256(data).hexdigest() == asset.sha256
                if valid:
                    asset.status = AssetStatus.READY
                    repaired += 1
                    continue
                storage.delete(asset.storage_key)
            asset.status = AssetStatus.FAILED
            asset.deleted_at = utc_now()
            failed += 1
        elif asset.status == AssetStatus.READY and not exists:
            asset.status = AssetStatus.FAILED
            asset.deleted_at = utc_now()
            failed += 1
    for key in storage.list_keys("users"):
        if key not in known_keys:
            storage.delete(key)
            orphans += 1
    session.commit()
    return {"repaired": repaired, "failed": failed, "orphans_deleted": orphans}

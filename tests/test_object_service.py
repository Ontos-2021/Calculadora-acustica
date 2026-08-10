from __future__ import annotations

from dataclasses import replace

import pytest

from api.db_models import LicenseTier
from api.licensing import authenticate_api_key
from api.object_service import (
    AssetIntegrityError,
    StorageQuotaExceeded,
    create_asset,
    delete_asset,
    get_asset,
    list_assets,
    read_asset,
    reconcile_assets,
    sanitize_filename,
    storage_usage,
    storage_metrics,
)
from api.storage import LocalStorage


PEPPER = "test-pepper-that-is-long-and-never-used-in-production"


def _principal(database, api_keys, tier=LicenseTier.PAID):
    principal = authenticate_api_key(database, api_keys[tier], pepper=PEPPER)
    assert principal is not None
    return principal


def test_asset_lifecycle_and_usage(api_session_factory, api_keys, tmp_path):
    storage = LocalStorage(tmp_path / "objects")
    with api_session_factory() as database:
        principal = _principal(database, api_keys)
        asset = create_asset(
            database,
            storage,
            principal,
            filename="../report.json",
            content_type="Application/JSON",
            data=b"report",
        )
        asset_id = asset.id
        assert asset.filename == "report.json"
        assert storage.get(asset.storage_key) == b"report"
        assert storage_usage(database, principal).used_bytes == 6
        assets, total = list_assets(database, principal)
        assert total == 1
        assert assets[0].id == asset_id
        assert get_asset(database, principal, asset_id).sha256
        delete_asset(database, storage, principal, asset_id)
        assert storage_usage(database, principal).used_bytes == 0


def test_asset_quota_is_enforced(api_session_factory, api_keys, tmp_path):
    storage = LocalStorage(tmp_path / "objects")
    with api_session_factory() as database:
        principal = replace(
            _principal(database, api_keys),
            quotas={"max_storage_bytes": 5},
        )
        with pytest.raises(StorageQuotaExceeded):
            create_asset(
                database,
                storage,
                principal,
                filename="large.bin",
                content_type=None,
                data=b"123456",
            )


def test_failed_storage_write_does_not_leave_metadata(
    api_session_factory, api_keys, tmp_path
):
    class FailingStorage(LocalStorage):
        def put(self, key, data, *, content_type=None):
            raise OSError("storage unavailable")

    storage = FailingStorage(tmp_path / "objects")
    with api_session_factory() as database:
        principal = _principal(database, api_keys)
        with pytest.raises(OSError):
            create_asset(
                database,
                storage,
                principal,
                filename="failed.bin",
                content_type=None,
                data=b"data",
            )
        assert storage_usage(database, principal).object_count == 0


def test_filename_sanitization():
    assert sanitize_filename("../../folder\\report.pdf") == "report.pdf"
    assert sanitize_filename("\r\n") == "file"


def test_read_verifies_integrity(api_session_factory, api_keys, tmp_path):
    storage = LocalStorage(tmp_path / "objects")
    with api_session_factory() as database:
        principal = _principal(database, api_keys)
        asset = create_asset(
            database, storage, principal, filename="x", content_type=None, data=b"ok"
        )
        storage.put(asset.storage_key, b"tampered")
        with pytest.raises(AssetIntegrityError):
            read_asset(database, storage, principal, asset.id)


def test_reconcile_removes_orphans(api_session_factory, tmp_path):
    storage = LocalStorage(tmp_path / "objects")
    storage.put("users/orphan/blob", b"orphan")
    with api_session_factory() as database:
        result = reconcile_assets(database, storage)
    assert result["orphans_deleted"] == 1
    assert not storage.exists("users/orphan/blob")


def test_storage_metrics_aggregate_status_and_category(
    api_session_factory, api_keys, tmp_path
):
    storage = LocalStorage(tmp_path / "objects")
    with api_session_factory() as database:
        principal = _principal(database, api_keys)
        create_asset(
            database,
            storage,
            principal,
            filename="report.pdf",
            content_type="application/pdf",
            data=b"pdf",
            category="export",
        )
        metrics = storage_metrics(database)
    assert metrics["by_status"]["READY"]["objects"] == 1
    assert metrics["by_category"]["export"]["bytes"] == 3

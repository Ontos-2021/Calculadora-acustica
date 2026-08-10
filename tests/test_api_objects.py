from __future__ import annotations


def test_object_api_lifecycle(client, free_headers):
    uploaded = client.post(
        "/api/v1/objects",
        files={"file": ("room.json", b'{"room": 1}', "application/json")},
        headers=free_headers,
    )
    assert uploaded.status_code == 201, uploaded.text
    asset = uploaded.json()
    assert asset["filename"] == "room.json"
    assert asset["size_bytes"] == 11

    listed = client.get("/api/v1/objects", headers=free_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    usage = client.get("/api/v1/objects/usage", headers=free_headers).json()
    assert usage["used_bytes"] == 11
    assert usage["remaining_bytes"] == usage["limit_bytes"] - 11

    metadata = client.get(
        f"/api/v1/objects/{asset['id']}", headers=free_headers
    )
    assert metadata.status_code == 200

    downloaded = client.get(
        f"/api/v1/objects/{asset['id']}/download", headers=free_headers
    )
    assert downloaded.content == b'{"room": 1}'
    assert "attachment" in downloaded.headers["content-disposition"]

    deleted = client.delete(
        f"/api/v1/objects/{asset['id']}", headers=free_headers
    )
    assert deleted.status_code == 204
    assert client.get(
        f"/api/v1/objects/{asset['id']}", headers=free_headers
    ).status_code == 404


def test_object_api_is_private(client, free_headers, paid_headers):
    uploaded = client.post(
        "/api/v1/objects",
        files={"file": ("private.txt", b"private", "text/plain")},
        headers=paid_headers,
    ).json()
    assert client.get(
        f"/api/v1/objects/{uploaded['id']}", headers=free_headers
    ).status_code == 404
    assert client.delete(
        f"/api/v1/objects/{uploaded['id']}", headers=free_headers
    ).status_code == 404


def test_object_api_requires_api_key(client):
    assert client.get("/api/v1/objects").status_code == 401
    assert client.post(
        "/api/v1/objects", files={"file": ("x", b"x")}
    ).status_code == 401


def test_storage_metrics_require_research(client, paid_headers, research_headers):
    assert client.get(
        "/api/v1/storage/metrics", headers=paid_headers
    ).status_code == 403
    response = client.get(
        "/api/v1/storage/metrics", headers=research_headers
    )
    assert response.status_code == 200
    assert response.json()["backend_available"] is True

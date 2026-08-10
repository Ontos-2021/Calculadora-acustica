from __future__ import annotations


def test_project_calculation_and_asset_flow(client, free_headers, paid_headers):
    assert client.get("/api/v1/projects", headers=free_headers).status_code == 403
    project_response = client.post(
        "/api/v1/projects",
        json={"name": "Studio A", "description": "Control room"},
        headers=paid_headers,
    )
    assert project_response.status_code == 201, project_response.text
    project = project_response.json()

    calculation = client.post(
        f"/api/v1/projects/{project['id']}/calculations",
        json={"kind": "room", "input_data": {"largo": 5}},
        headers=paid_headers,
    )
    assert calculation.status_code == 201

    asset = client.post(
        "/api/v1/objects",
        files={"file": ("report.pdf", b"pdf", "application/pdf")},
        data={"category": "export"},
        headers=paid_headers,
    ).json()
    attached = client.post(
        f"/api/v1/projects/{project['id']}/objects/{asset['id']}",
        headers=paid_headers,
    )
    assert attached.status_code == 200
    assert attached.json()["category"] == "export"
    assert len(
        client.get(
            f"/api/v1/projects/{project['id']}/objects", headers=paid_headers
        ).json()
    ) == 1

    updated = client.patch(
        f"/api/v1/projects/{project['id']}",
        json={"archived": True},
        headers=paid_headers,
    )
    assert updated.json()["archived"] is True
    assert client.delete(
        f"/api/v1/projects/{project['id']}", headers=paid_headers
    ).status_code == 204

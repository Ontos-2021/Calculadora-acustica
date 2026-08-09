from __future__ import annotations

import uuid

import pytest

from api.db_models import LicenseTier
from api.jobs import InMemoryJobQueue, enqueue_job
from api.licensing import authenticate_api_key


TEST_API_KEY_PEPPER = "test-pepper-that-is-long-and-never-used-in-production"


def test_owner_scoped_job_status_and_cancel(
    client,
    api_session_factory,
    api_keys,
    free_headers,
    paid_headers,
    research_headers,
):
    with api_session_factory() as database:
        principal = authenticate_api_key(
            database,
            api_keys[LicenseTier.PAID],
            pepper=TEST_API_KEY_PEPPER,
        )
        assert principal is not None
        job = enqueue_job(
            database,
            InMemoryJobQueue(),
            "report.render",
            {"calculation_id": "test"},
            principal=principal,
        )
        job_id = job.id

    path = f"/api/v1/jobs/{job_id}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=free_headers).status_code == 403
    assert client.get(path, headers=research_headers).status_code == 404

    status_response = client.get(path, headers=paid_headers)
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "QUEUED"
    assert status_response.json()["kind"] == "report.render"

    cancelled = client.delete(path, headers=paid_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert client.delete(path, headers=paid_headers).status_code == 409


def test_unknown_job_is_404_only_after_authorization(client, free_headers, paid_headers):
    path = f"/api/v1/jobs/{uuid.uuid4()}"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=free_headers).status_code == 403
    assert client.get(path, headers=paid_headers).status_code == 404


def test_polygon_fem_requires_research_entitlement(
    client, paid_headers, research_headers
):
    payload = {
        "vertices": [[0, 0], [2, 0], [2, 1.5], [0, 1.5]],
        "target_edge_length_m": 0.75,
        "num_modes": 1,
        "room_height_m": 3,
        "max_vertical_order": 1,
    }
    assert client.post("/api/v1/numerical/fem2d/polygon", json=payload).status_code == 401
    assert client.post(
        "/api/v1/numerical/fem2d/polygon", json=payload, headers=paid_headers
    ).status_code == 403

    response = client.post(
        "/api/v1/numerical/fem2d/polygon",
        json=payload,
        headers=research_headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["modes"]
    assert response.json()["coupled_modes"]
    assert "Research" in response.json()["research_status"]


def test_finite_impedance_uses_environment_sound_speed(client, paid_headers):
    base = {
        "L_m": 5,
        "W_m": 4,
        "H_m": 3,
        "Z_wall": 10000,
        "max_order": 1,
    }
    cold = client.post(
        "/api/v1/numerical/finite-impedance",
        json={**base, "environment": {"temperature_c": 0, "relative_humidity": 0}},
        headers=paid_headers,
    )
    warm = client.post(
        "/api/v1/numerical/finite-impedance",
        json={**base, "environment": {"temperature_c": 30, "relative_humidity": 80}},
        headers=paid_headers,
    )

    assert cold.status_code == 200, cold.text
    assert warm.status_code == 200, warm.text
    assert warm.json()["environment"]["sound_speed_m_s"] > cold.json()["environment"]["sound_speed_m_s"]
    assert warm.json()["axial_modes"][0]["rigid_frequency_hz"] > cold.json()["axial_modes"][0]["rigid_frequency_hz"]


def test_seeded_ray_route_reports_direct_environment_timing(client, paid_headers):
    payload = {
        "largo": 5,
        "ancho": 4,
        "alto": 3,
        "superficies": [{"material": "Concreto"}] * 6,
        "source": [1, 1, 1.2],
        "receiver": [4, 3, 1.2],
        "num_rays": 50,
        "max_reflections": 1,
        "max_time_s": 0.1,
        "seed": 23,
        "environment": {"temperature_c": 10, "relative_humidity": 40},
    }
    response = client.post(
        "/api/v1/numerical/ray-tracing", json=payload, headers=paid_headers
    )

    assert response.status_code == 200, response.text
    data = response.json()
    expected = (13**0.5) / data["environment"]["sound_speed_m_s"]
    assert data["seed"] == 23
    assert data["direct_time_s"] == pytest.approx(expected)

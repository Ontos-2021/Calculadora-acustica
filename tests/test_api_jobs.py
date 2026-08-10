from __future__ import annotations

import uuid

import pytest

from api.db_models import LicenseTier
from api.jobs import InMemoryJobQueue, enqueue_job, process_next_job
from api.licensing import authenticate_api_key


TEST_API_KEY_PEPPER = "test-pepper-that-is-long-and-never-used-in-production"


FEM2D_SUBMIT_PAYLOAD = {
    "width": 5,
    "height": 4,
    "grid_nx": 6,
    "grid_ny": 6,
    "num_modes": 1,
}


def _submit_job(
    client, headers, *, kind="numerical.fem2d", payload=None, idempotency_key=None
):
    return client.post(
        "/api/v1/jobs",
        json={
            "kind": kind,
            "payload": payload if payload is not None else FEM2D_SUBMIT_PAYLOAD,
            "idempotency_key": idempotency_key,
        },
        headers=headers,
    )


def test_submit_job_requires_jobs_entitlement(
    client, free_headers, paid_headers, research_headers
):
    assert _submit_job(client, {}).status_code == 401
    assert _submit_job(client, free_headers).status_code == 403
    assert _submit_job(client, paid_headers).status_code == 200
    assert _submit_job(client, research_headers).status_code == 200


def test_submit_job_rejects_unknown_kind(client, paid_headers):
    response = _submit_job(client, paid_headers, kind="unknown.kind")
    assert response.status_code == 422


def test_submit_job_rejects_payload_that_does_not_match_kind(client, paid_headers):
    response = _submit_job(client, paid_headers, payload={"grid_nx": 2})
    assert response.status_code == 422


def test_submit_job_queued_and_owner_visible(client, api_session_factory, paid_headers):
    queued = _submit_job(client, paid_headers).json()
    assert queued["status"] == "QUEUED"
    assert queued["kind"] == "numerical.fem2d"
    assert queued["attempts"] == 0

    status = client.get(f"/api/v1/jobs/{queued['id']}", headers=paid_headers)
    assert status.status_code == 200
    assert status.json()["status"] == "QUEUED"


def test_submit_job_idempotency_key_returns_same_job(client, paid_headers):
    first = _submit_job(client, paid_headers, idempotency_key="render-fem-1").json()
    second = _submit_job(client, paid_headers, idempotency_key="render-fem-1").json()
    assert first["id"] == second["id"]


def test_submit_job_enforces_max_concurrent_jobs(api_context, paid_headers):
    client = api_context.client
    job_ids = [
        _submit_job(client, paid_headers, idempotency_key=f"batch-{index}").json()["id"]
        for index in range(5)
    ]
    assert len(job_ids) == 5

    blocked = _submit_job(client, paid_headers, idempotency_key="batch-6")
    assert blocked.status_code == 429


def test_cancel_queued_job_returns_concurrency_slot(client, api_context, paid_headers):
    response = _submit_job(client, paid_headers, idempotency_key="queue-and-cancel")
    assert response.status_code == 200
    job_id = response.json()["id"]

    cancelled = client.delete(f"/api/v1/jobs/{job_id}", headers=paid_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"

    again = _submit_job(client, paid_headers, idempotency_key="queue-and-cancel-2")
    assert again.status_code == 200


def test_worker_processes_fem2d_job_with_registered_handler(
    api_context, api_session_factory, paid_headers
):
    from api.jobs import get_job_status
    from worker.handlers import JOB_HANDLERS

    submitted = _submit_job(
        api_context.client, paid_headers, idempotency_key="worker-fem2d"
    ).json()
    job_id = submitted["id"]

    processed = process_next_job(
        api_session_factory,
        api_context.job_queue,
        JOB_HANDLERS,
    )

    assert processed is True
    with api_session_factory() as database:
        view = get_job_status(database, uuid.UUID(job_id))
    assert view is not None
    assert view.status.value == "SUCCEEDED"
    assert view.error is None
    assert view.attempts == 1
    assert view.result is not None
    assert len(view.result["modes"]) == 1
    assert view.result["width"] == 5


def test_worker_fails_job_without_registered_handler(
    api_context, api_session_factory, api_keys
):
    from api.jobs import get_job_status
    from worker.handlers import JOB_HANDLERS

    with api_session_factory() as database:
        principal = authenticate_api_key(
            database,
            api_keys[LicenseTier.PAID],
            pepper=TEST_API_KEY_PEPPER,
        )
        assert principal is not None
        job = enqueue_job(
            database,
            api_context.job_queue,
            "report.render",
            {"calculation_id": "test"},
            principal=principal,
        )
        job_id = job.id

    processed = process_next_job(
        api_session_factory,
        api_context.job_queue,
        JOB_HANDLERS,
    )
    assert processed is True
    with api_session_factory() as database:
        view = get_job_status(database, job_id)
    assert view is not None
    assert view.status.value == "FAILED"
    assert "No worker handler registered" in (view.error or "")


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


def test_unknown_job_is_404_only_after_authorization(
    client, free_headers, paid_headers
):
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
    assert (
        client.post("/api/v1/numerical/fem2d/polygon", json=payload).status_code == 401
    )
    assert (
        client.post(
            "/api/v1/numerical/fem2d/polygon", json=payload, headers=paid_headers
        ).status_code
        == 403
    )

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
    assert (
        warm.json()["environment"]["sound_speed_m_s"]
        > cold.json()["environment"]["sound_speed_m_s"]
    )
    assert (
        warm.json()["axial_modes"][0]["rigid_frequency_hz"]
        > cold.json()["axial_modes"][0]["rigid_frequency_hz"]
    )


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

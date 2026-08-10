from __future__ import annotations

import pytest


def room_payload(**overrides):
    payload = {
        "largo": 5,
        "ancho": 4,
        "alto": 3,
        "superficies": [{"material": "Concreto"}] * 6,
    }
    payload.update(overrides)
    return payload


PAID_CASES = [
    ("GET", "/api/v1/materials", None),
    (
        "POST",
        "/api/v1/design/inverse",
        room_payload(target_uso="home_studio"),
    ),
    (
        "POST",
        "/api/v1/design/absorbers/membrane",
        {"mass_per_area_kgm2": 10, "air_gap_m": 0.1},
    ),
    (
        "POST",
        "/api/v1/design/diffusers/qrd",
        {"design_freq_hz": 1000, "prime_n": 7, "well_width_m": 0.05},
    ),
    (
        "POST",
        "/api/v1/design/isolation/flanking",
        {"direct_tl_db": 50, "flanking_paths_tl_db": [55]},
    ),
    (
        "POST",
        "/api/v1/impulse-response",
        room_payload(
            source=[1, 1, 1.5],
            receiver=[4, 3, 1.2],
            max_order=0,
            sample_rate=8000,
            duration_s=0.05,
        ),
    ),
    (
        "POST",
        "/api/v1/measurement/ess",
        {
            "f1_hz": 100,
            "f2_hz": 1000,
            "duration_s": 0.02,
            "sample_rate": 8000,
        },
    ),
    (
        "POST",
        "/api/v1/numerical/finite-impedance",
        {"L_m": 5, "W_m": 4, "H_m": 3, "Z_wall": 10000, "max_order": 1},
    ),
]


@pytest.mark.parametrize("method,path,payload", PAID_CASES)
def test_paid_route_entitlement_matrix(
    client, free_headers, paid_headers, method, path, payload
):
    missing = client.request(method, path, json=payload)
    free = client.request(method, path, json=payload, headers=free_headers)
    paid = client.request(method, path, json=payload, headers=paid_headers)

    assert missing.status_code == 401
    assert free.status_code == 403
    assert paid.status_code == 200, paid.text


def test_public_calculation_and_pressure_map_are_anonymous_and_rate_limited(client):
    calculation = client.post("/api/v1/calculate", json=room_payload())
    pressure = client.post(
        "/api/v1/pressure-map",
        json=room_payload(max_freq=100, grid_size=10, mode_indices=[1, 0, 0]),
    )

    assert calculation.status_code == 200
    assert pressure.status_code == 200
    assert calculation.headers["X-RateLimit-Tier"] == "ANONYMOUS"
    assert pressure.headers["X-RateLimit-Cost"] == "5"
    assert pressure.json()["signed_pressure"] is not None


def test_calculate_exposes_new_structured_results_without_breaking_legacy_fields(client):
    payload = room_payload(
        environment={
            "temperature_c": 10,
            "relative_humidity": 40,
            "pressure_pa": 90000,
        }
    )
    payload["superficies"][0] = {
        "material": "Concreto",
        "alphas": {"125": 0.25},
    }
    response = client.post("/api/v1/calculate", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["modos"] and data["rt60_bandas"]
    assert data["environment"]["temperature_c"] == 10
    assert data["sound_speed_m_s"] == data["environment"]["sound_speed_m_s"]
    assert "is_diffuse" in data["diffuse_field"]
    assert "is_inside" in data["bolt_area"]
    assert any(item["code"] == "partial_absorption_merged" for item in data["method_warnings"])


def test_unknown_material_is_not_silently_replaced(client):
    unknown = client.post(
        "/api/v1/calculate",
        json=room_payload(
            superficies=[{"material": "Unobtainium"}] + [{"material": "Concreto"}] * 5
        ),
    )
    custom = client.post(
        "/api/v1/calculate",
        json=room_payload(
            superficies=[
                {
                    "material": "Measured custom finish",
                    "alphas": {
                        "125": 0.1,
                        "250": 0.2,
                        "500": 0.3,
                        "1000": 0.4,
                        "2000": 0.5,
                        "4000": 0.6,
                    },
                }
            ]
            + [{"material": "Concreto"}] * 5
        ),
    )

    assert unknown.status_code == 422
    assert "Unknown material" in unknown.json()["detail"]
    assert custom.status_code == 200


@pytest.mark.parametrize(
    "path,payload",
    [
        ("/api/v1/pressure-map", room_payload(mode_indices=[1, 0])),
        (
            "/api/v1/impulse-response",
            room_payload(source=[0, 1, 1], receiver=[4, 3, 1.2]),
        ),
        (
            "/api/v1/measurement/ess",
            {"f1_hz": 1000, "f2_hz": 4000, "sample_rate": 8000, "duration_s": 1},
        ),
    ],
)
def test_cross_field_validation_rejects_invalid_data(client, paid_headers, path, payload):
    response = client.post(path, json=payload, headers=paid_headers)
    assert response.status_code == 422


def test_fem_exclusion_contract_is_validated(client, paid_headers):
    malformed = client.post(
        "/api/v1/numerical/fem2d",
        json={"width": 5, "height": 4, "exclude_region": "1,2,bad,3"},
        headers=paid_headers,
    )
    outside = client.post(
        "/api/v1/numerical/fem2d",
        json={
            "width": 5,
            "height": 4,
            "exclude_regions": [{"x0": 1, "y0": 1, "x1": 6, "y1": 2}],
        },
        headers=paid_headers,
    )
    assert malformed.status_code == 422
    assert outside.status_code == 422


def test_license_status_and_authentication_semantics(client, free_headers):
    assert client.get("/api/v1/license/status").status_code == 401
    assert client.get(
        "/api/v1/license/status", headers={"X-API-Key": "free_tier"}
    ).status_code == 401

    response = client.get("/api/v1/license/status", headers=free_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "FREE"
    assert data["authenticated"] is True
    assert set(data["entitlements"]) == {"basic", "pressure_map", "storage"}
    assert data["quotas"]["requests_per_minute"] == 30


def test_limited_public_material_catalog_and_paid_full_catalog(client, paid_headers):
    defaults = client.get("/api/v1/materials/defaults")
    full = client.get("/api/v1/materials", headers=paid_headers)

    assert defaults.status_code == 200
    assert 1 <= len(defaults.json()) < len(full.json())
    assert any(material["nombre"] == "Concreto" for material in defaults.json())


def test_openapi_declares_api_key_security_and_optional_public_auth(client):
    schema = client.get("/openapi.json").json()
    scheme = schema["components"]["securitySchemes"]["APIKeyHeader"]
    paid_security = schema["paths"]["/api/v1/materials"]["get"]["security"]
    public_security = schema["paths"]["/api/v1/calculate"]["post"]["security"]

    assert scheme == {"type": "apiKey", "in": "header", "name": "X-API-Key"}
    assert {"APIKeyHeader": []} in paid_security
    assert {} in public_security
    assert {"APIKeyHeader": []} in public_security


def test_material_and_audience_diagnostics_are_not_filtered(client, paid_headers):
    material = client.get(
        "/api/v1/materials/Concreto", headers=paid_headers
    )
    classification = client.post(
        "/api/v1/materials/classify-iso11654",
        json={
            "practical_coefficients": {
                "250": 0.35,
                "500": 0.60,
                "1000": 0.85,
                "2000": 0.90,
                "4000": 0.90,
            }
        },
        headers=paid_headers,
    )
    audience = client.post(
        "/api/v1/design/audience-absorption/details",
        json={"num_people": 20, "occupied": 0.75, "upholstered": False},
        headers=paid_headers,
    )

    assert material.status_code == 200, material.text
    assert material.json()["catalog"]["mounting_condition"]
    assert material.json()["uncertainty"]["expanded"] > 0
    assert classification.status_code == 200, classification.text
    assert classification.json()["designation"].startswith("alpha_w")
    assert audience.status_code == 200, audience.text
    assert audience.json()["occupied_people_equivalent"] == 15
    assert audience.json()["assumptions"]


def test_detailed_absorber_and_diffuser_contracts(client, paid_headers):
    porous = client.post(
        "/api/v1/design/absorbers/porous",
        json={
            "thickness_m": 0.05,
            "flow_resistivity": 10000,
            "density_kgm3": None,
            "air_gap_m": 0.05,
        },
        headers=paid_headers,
    )
    diffusion = client.post(
        "/api/v1/design/diffusers/diffusion",
        json={
            "polar_response": [1, 1, 0, 0],
            "reference_response": [1, 0, 0, 0],
            "response_unit": "pressure",
        },
        headers=paid_headers,
    )

    assert porous.status_code == 200, porous.text
    assert porous.json()["quarter_wave_effective_depth_m"] == 0.1
    assert "valid_by_band" in porous.json()
    assert diffusion.status_code == 200, diffusion.text
    assert diffusion.json()["normalized_diffusion_coefficient"] == pytest.approx(1 / 3)


def test_inverse_verification_and_bounded_optimization(client, paid_headers):
    target = {band: 0.8 for band in ("125", "250", "500", "1000", "2000", "4000")}
    verification = client.post(
        "/api/v1/design/inverse/verify",
        json=room_payload(
            target_rt60=target,
            treatments=[
                {
                    "material": "Lana mineral (100mm)",
                    "area_m2": 5,
                    "surface_index": 0,
                    "installation_mode": "replacement",
                }
            ],
        ),
        headers=paid_headers,
    )
    optimization = client.post(
        "/api/v1/design/inverse/optimize",
        json=room_payload(
            target_uso="sala_conferencias",
            candidate_materials=["Lana mineral (100mm)"],
            available_area_m2=5,
            area_step_m2=1,
        ),
        headers=paid_headers,
    )

    assert verification.status_code == 200, verification.text
    assert verification.json()["aggregation_rule"]
    assert optimization.status_code == 200, optimization.text
    assert optimization.json()["used_area_m2"] <= 5
    assert optimization.json()["forward_verification"]["predicted_rt60_s"]

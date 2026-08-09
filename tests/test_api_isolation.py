from __future__ import annotations

from acoustic_core.isolation import NR_FREQS, THIRD_OCTAVE_BANDS_HZ


def _band_key(frequency):
    return str(int(frequency)) if float(frequency).is_integer() else str(frequency)


def test_complete_third_octave_ratings_expose_stc_rw_c_ctr(client, paid_headers):
    curve = {
        _band_key(frequency): 35 + index * 1.5
        for index, frequency in enumerate(THIRD_OCTAVE_BANDS_HZ)
    }
    response = client.post(
        "/api/v1/design/isolation/ratings",
        json={"tl": curve},
        headers=paid_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["stc"]["input_complete"] is True
    assert data["rw"]["input_complete"] is True
    assert isinstance(data["stc"]["stc"], int)
    assert isinstance(data["rw"]["rw"], int)
    assert isinstance(data["rw"]["c"], int)
    assert isinstance(data["rw"]["ctr"], int)


def test_partial_third_octave_rating_curve_is_rejected(client, paid_headers):
    response = client.post(
        "/api/v1/design/isolation/ratings",
        json={"tl": {"125": 40, "250": 45, "500": 50}},
        headers=paid_headers,
    )
    assert response.status_code == 422


def test_nr_and_target_comparison_endpoints(client, paid_headers):
    nr = client.post(
        "/api/v1/design/isolation/nr",
        json={"spl": {_band_key(frequency): 30 for frequency in NR_FREQS}},
        headers=paid_headers,
    )
    comparison = client.post(
        "/api/v1/design/isolation/target-comparison",
        json={"uso": "aula", "nr": 30, "stc": 55, "rw": 52},
        headers=paid_headers,
    )

    assert nr.status_code == 200, nr.text
    assert nr.json()["classification"].startswith("NR-")
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["meets_all_targets"] is True
    assert comparison.json()["comparisons"]["stc"]["target_min"] == 50


def test_duct_and_flanking_engineering_estimates(client, paid_headers):
    duct = client.post(
        "/api/v1/design/isolation/duct-attenuation",
        json={
            "width_m": 0.5,
            "height_m": 0.3,
            "length_m": 2,
            "absorption_coefficients": 0.5,
        },
        headers=paid_headers,
    )
    flanking = client.post(
        "/api/v1/design/isolation/flanking",
        json={
            "direct_tl_db": {"125": 45, "250": 50},
            "flanking_paths_tl_db": [{"125": 50, "250": 55}],
        },
        headers=paid_headers,
    )

    assert duct.status_code == 200, duct.text
    assert set(duct.json()["insertion_loss_db"]) == {
        "125", "250", "500", "1000", "2000", "4000"
    }
    assert duct.json()["is_estimate"] is True
    assert flanking.status_code == 200, flanking.text
    assert flanking.json()["apparent_tl_db"]["125"] < 45
    assert flanking.json()["not_iso_12354_prediction"] is True


def test_legacy_single_panel_now_contains_complete_ratings(client, paid_headers):
    response = client.post(
        "/api/v1/design/isolation/single-panel",
        json={
            "mass_per_area_kgm2": 50,
            "thickness_m": 0.1,
            "material_type": "concreto",
        },
        headers=paid_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert len(data["tl"]) == 6
    assert len(data["third_octave_tl"]) == len(THIRD_OCTAVE_BANDS_HZ)
    assert data["stc_details"]["input_complete"] is True
    assert data["rw_details"]["input_complete"] is True

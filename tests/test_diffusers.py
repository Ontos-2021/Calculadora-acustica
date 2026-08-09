import pytest
from acoustic_core.diffusers import (
    diffusion_coefficient_diagnostics,
    estimate_diffusion_coefficient,
    estimate_diffusion_coefficient_heuristic,
    nearest_prime,
    normalized_diffusion_coefficient,
    polar_diffusion_coefficient,
    qrd_well_depths,
    simulate_qrd_polar_response,
    skyline_well_depths,
)


class TestQRD:
    def test_basic(self):
        result = qrd_well_depths(1000, 17)
        assert result["prime_n"] == 17
        assert len(result["well_depths_m"]) == 17
        assert result["type"] == "QRD"

    def test_depth_positive(self):
        result = qrd_well_depths(1000, 17)
        assert all(d >= 0 for d in result["well_depths_m"])

    def test_sequence_correct(self):
        result = qrd_well_depths(1000, 7)
        expected_seq = [(n * n) % 7 for n in range(7)]
        assert result["sequence"] == expected_seq

    def test_approx_nearest_prime(self):
        result = qrd_well_depths(1000, 16)
        assert result["prime_n"] == 17

    def test_true_nearest_prime_can_be_lower(self):
        assert nearest_prime(14) == 13
        assert nearest_prime(12) == 11
        assert nearest_prime(202) == 199
        assert qrd_well_depths(1000, 14)["prime_n"] == 13

    def test_total_width(self):
        result = qrd_well_depths(1000, 17, 0.1)
        assert result["total_width_m"] == pytest.approx(1.7, rel=0.01)

    def test_invalid_params(self):
        result = qrd_well_depths(0, 17)
        assert "error" in result

    def test_useful_band_and_manufacturability_follow_well_width(self):
        narrow = qrd_well_depths(1000, 17, 0.05)
        wide = qrd_well_depths(1000, 17, 0.20)
        assert narrow["lower_useful_frequency_hz"] == pytest.approx(1000)
        assert narrow["upper_useful_frequency_hz"] == pytest.approx(3430)
        assert wide["upper_useful_frequency_hz"] < wide["lower_useful_frequency_hz"]
        assert wide["manufacturability"]["manufacturable"] is False

    def test_generated_depth_formula(self):
        result = qrd_well_depths(1000, 7)
        expected = result["sequence"][3] * 343 / (2 * 7 * 1000)
        assert result["well_depths_m"][3] == pytest.approx(expected, abs=5e-5)


class TestSkyline:
    def test_basic(self):
        result = skyline_well_depths(1000, 7)
        assert result["grid_n"] == 7
        assert len(result["well_depths_m"]) == 7
        assert len(result["well_depths_m"][0]) == 7
        assert result["type"] == "Skyline"

    def test_invalid_params(self):
        result = skyline_well_depths(0, 7)
        assert "error" in result

    def test_uses_two_dimensional_quadratic_residues(self):
        result = skyline_well_depths(1000, 7)
        expected = [
            [((row * row) + (column * column)) % 7 for column in range(7)]
            for row in range(7)
        ]
        assert result["sequence_2d"] == expected
        assert "i^2 + j^2" in result["construction"]

    def test_skyline_uses_nearest_prime_grid(self):
        result = skyline_well_depths(1000, 6)
        assert result["requested_grid_n"] == 6
        assert result["grid_n"] == 5
        assert len(result["well_depths_m"]) == 5


class TestDiffusionCoefficient:
    def test_basic(self):
        coeff = estimate_diffusion_coefficient(1000, 0.1715)
        assert len(coeff) == 6
        assert all(0 <= v <= 1 for v in coeff.values())

    def test_peak_near_design(self):
        coeff = estimate_diffusion_coefficient(1000, 0.1715)
        assert coeff["1000"] > coeff["125"]

    def test_symmetric(self):
        coeff = estimate_diffusion_coefficient(1000, 0.1715)
        assert all(0 <= v <= 1 for v in coeff.values())

    def test_heuristic_is_geometry_sensitive(self):
        shallow = estimate_diffusion_coefficient_heuristic(1000, 0.03)
        deep = estimate_diffusion_coefficient_heuristic(1000, 0.17)
        assert deep["500"] > shallow["500"]
        assert deep["1000"] > shallow["1000"]


class TestPolarDiffusionCoefficient:
    def test_uniform_and_single_lobe_identities(self):
        assert polar_diffusion_coefficient([1, 1, 1, 1]) == pytest.approx(1)
        assert polar_diffusion_coefficient([1, 0, 0, 0]) == pytest.approx(0)

    def test_known_normalized_energy_formula(self):
        # Pressure [1, 1, 0, 0] gives energies [1, 1, 0, 0]:
        # ((2)^2 - 2) / ((4-1)*2) = 1/3.
        coefficient = normalized_diffusion_coefficient([1, 1, 0, 0])
        assert coefficient == pytest.approx(1 / 3)

    def test_reference_surface_normalization(self):
        coefficient = normalized_diffusion_coefficient(
            [1, 1, 0, 0],
            reference_response=[1, 0, 0, 0],
        )
        assert coefficient == pytest.approx(1 / 3)
        diagnostics = diffusion_coefficient_diagnostics(
            [1, 1, 0, 0],
            reference_response=[1, 0, 0, 0],
        )
        assert diagnostics["normalized_diffusion_coefficient"] == pytest.approx(1 / 3)
        assert "not" in diagnostics["implementation_note"].lower()

    def test_db_and_energy_inputs(self):
        db = polar_diffusion_coefficient([0, 0, -300, -300], response_unit="db")
        energy = polar_diffusion_coefficient([1, 1, 0, 0], response_unit="energy")
        assert db == pytest.approx(energy)

    def test_simulated_qrd_response_drives_public_formula(self):
        geometry = qrd_well_depths(1000, 7, 0.05)
        polar = simulate_qrd_polar_response(
            geometry["well_depths_m"],
            1000,
            geometry["well_width_m"],
        )
        coefficient = normalized_diffusion_coefficient(polar)
        assert len(polar) == 37
        assert 0 <= coefficient <= 1


class TestDiffuserAPI:
    def test_qrd_endpoint(self, client, paid_headers):
        response = client.post("/api/v1/design/diffusers/qrd", json={
            "design_freq_hz": 1000, "prime_n": 17, "well_width_m": 0.05,
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "QRD"
        assert len(data["well_depths_m"]) == 17
        assert "diffusion_coefficient" in data

    def test_skyline_endpoint(self, client, paid_headers):
        response = client.post("/api/v1/design/diffusers/skyline", json={
            "design_freq_hz": 1000, "grid_n": 7, "well_size_m": 0.05,
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "Skyline"
        assert len(data["well_depths_m"]) == 7

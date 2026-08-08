import pytest
from acoustic_core.diffusers import qrd_well_depths, skyline_well_depths, estimate_diffusion_coefficient


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
        assert result["prime_n"] == 17  # nearest prime >= 16

    def test_total_width(self):
        result = qrd_well_depths(1000, 17, 0.1)
        assert result["total_width_m"] == pytest.approx(1.7, rel=0.01)

    def test_invalid_params(self):
        result = qrd_well_depths(0, 17)
        assert "error" in result


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


class TestDiffuserAPI:
    def test_qrd_endpoint(self, client):
        response = client.post("/api/v1/design/diffusers/qrd", json={
            "design_freq_hz": 1000, "prime_n": 17, "well_width_m": 0.05,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "QRD"
        assert len(data["well_depths_m"]) == 17
        assert "diffusion_coefficient" in data

    def test_skyline_endpoint(self, client):
        response = client.post("/api/v1/design/diffusers/skyline", json={
            "design_freq_hz": 1000, "grid_n": 7, "well_size_m": 0.05,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "Skyline"
        assert len(data["well_depths_m"]) == 7

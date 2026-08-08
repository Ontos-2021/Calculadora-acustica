import pytest
from acoustic_core.absorbers import porous_absorption, helmholtz_resonator, membrane_absorber


class TestPorous:
    def test_basic_absorption(self):
        alpha = porous_absorption(0.05, 10000)
        assert len(alpha) == 6
        assert all(0 <= v <= 1 for v in alpha.values())

    def test_thicker_absorbs_more_at_low(self):
        thin = porous_absorption(0.025, 10000)
        thick = porous_absorption(0.10, 10000)
        assert thick["125"] > thin["125"]

    def test_invalid_params(self):
        alpha = porous_absorption(0, 10000)
        assert all(v == 0 for v in alpha.values())


class TestHelmholtz:
    def test_resonance_frequency(self):
        result = helmholtz_resonator(0.01, 0.1, 0.05)
        assert result["f0"] > 0
        assert result["Q"] > 0

    def test_peak_at_resonance(self):
        # params tuned so f0 ≈ 546 Hz, closest band is 500 Hz
        result = helmholtz_resonator(0.01, 0.001, 0.1)
        f0 = result["f0"]
        alpha = result["alpha"]
        bands = [125, 250, 500, 1000, 2000, 4000]
        closest = min(bands, key=lambda b: abs(b - f0))
        key = str(closest)
        assert alpha[key] > 0.8, f"f0={f0}, alpha[500]={alpha['500']}"

    def test_invalid_params(self):
        result = helmholtz_resonator(0, 0.1, 0.05)
        assert result["f0"] == 0


class TestMembrane:
    def test_resonance_frequency(self):
        result = membrane_absorber(10, 0.1)
        assert result["f0"] > 0
        expected = 60 / (10 * 0.1) ** 0.5
        assert abs(result["f0"] - expected) < 0.1

    def test_invalid_params(self):
        result = membrane_absorber(0, 0.1)
        assert result["f0"] == 0


class TestAbsorberAPI:
    def test_porous_endpoint(self, client):
        response = client.post("/api/v1/design/absorbers/porous", json={
            "thickness_m": 0.05, "flow_resistivity": 10000, "density_kgm3": 100,
        })
        assert response.status_code == 200
        data = response.json()
        assert "alpha" in data
        assert len(data["alpha"]) == 6

    def test_helmholtz_endpoint(self, client):
        response = client.post("/api/v1/design/absorbers/helmholtz", json={
            "neck_area_m2": 0.01, "cavity_volume_m3": 0.001, "neck_length_m": 0.1,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["f0"] > 0

    def test_membrane_endpoint(self, client):
        response = client.post("/api/v1/design/absorbers/membrane", json={
            "mass_per_area_kgm2": 10, "air_gap_m": 0.1,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["f0"] > 0

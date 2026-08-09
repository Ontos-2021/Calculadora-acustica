import pytest
from acoustic_core.absorbers import (
    helmholtz_resonator,
    membrane_absorber,
    porous_absorber_estimate,
    porous_absorption,
    recommended_absorber_area,
)


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

    def test_quarter_wave_and_delany_bazley_validity_are_reported(self):
        with pytest.warns(DeprecationWarning, match="ignored"):
            result = porous_absorber_estimate(0.05, 10000, density_kgm3=80)
        assert result["quarter_wave_frequency_hz"] == pytest.approx(1715, rel=1e-4)
        assert result["density_input_used"] is False
        assert result["valid_for_all_bands"] is True
        assert all(0 <= value <= 1 for value in result["alpha"].values())
        assert "estimate" in result["estimate_label"]

    def test_strict_delany_bazley_range_rejects_extrapolation(self):
        with pytest.raises(ValueError, match="125 Hz"):
            porous_absorber_estimate(
                0.05,
                1_000_000,
                density_kgm3=None,
                strict_validity=True,
            )

    def test_deprecated_bulk_density_does_not_change_curve(self):
        with pytest.warns(DeprecationWarning):
            light = porous_absorption(0.05, 10000, density_kgm3=30)
        with pytest.warns(DeprecationWarning):
            heavy = porous_absorption(0.05, 10000, density_kgm3=200)
        assert light == heavy

    def test_air_gap_changes_low_frequency_estimate(self):
        no_gap = porous_absorber_estimate(0.05, 10000, density_kgm3=None)
        gap = porous_absorber_estimate(
            0.05, 10000, density_kgm3=None, air_gap_m=0.05
        )
        assert gap["quarter_wave_frequency_hz"] < no_gap["quarter_wave_frequency_hz"]
        assert gap["alpha"]["125"] > no_gap["alpha"]["125"]

    def test_flow_resistivity_changes_estimated_curve(self):
        low = porous_absorber_estimate(0.05, 5000, density_kgm3=None)
        high = porous_absorber_estimate(0.05, 30000, density_kgm3=None)
        assert low["alpha"] != high["alpha"]


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

    def test_open_area_can_define_total_neck_area(self):
        result = helmholtz_resonator(
            None,
            0.1,
            0.02,
            neck_radius_m=0.003,
            panel_area_m2=0.5,
            open_area_ratio=0.02,
        )
        assert result["neck_area_m2"] == pytest.approx(0.01)
        assert result["effective_hole_count"] > 300
        assert result["open_area_ratio"] == pytest.approx(0.02)

    def test_explicit_hole_geometry_must_be_consistent(self):
        with pytest.raises(ValueError, match="inconsistent"):
            helmholtz_resonator(
                0.01,
                0.1,
                0.02,
                neck_radius_m=0.01,
                hole_count=2,
            )

    def test_end_correction_radius_changes_resonance(self):
        small_holes = helmholtz_resonator(0.01, 0.1, 0.02, neck_radius_m=0.002)
        large_holes = helmholtz_resonator(0.01, 0.1, 0.02, neck_radius_m=0.02)
        assert small_holes["f0"] > large_holes["f0"]

    def test_configurable_losses_change_bandwidth(self):
        narrow = helmholtz_resonator(
            0.01, 0.001, 0.1, quality_factor=10
        )
        broad = helmholtz_resonator(
            0.01, 0.001, 0.1, quality_factor=1
        )
        assert narrow["Q"] > broad["Q"]
        assert narrow["alpha"]["1000"] < broad["alpha"]["1000"]
        assert all(0 <= value <= 1 for value in narrow["alpha"].values())


class TestMembrane:
    def test_resonance_frequency(self):
        result = membrane_absorber(10, 0.1)
        assert result["f0"] > 0
        expected = 60 / (10 * 0.1) ** 0.5
        assert abs(result["f0"] - expected) < 0.1

    def test_invalid_params(self):
        result = membrane_absorber(0, 0.1)
        assert result["f0"] == 0

    def test_tension_increases_resonance_and_is_disclosed(self):
        untensioned = membrane_absorber(5, 0.1)
        tensioned = membrane_absorber(
            5,
            0.1,
            surface_tension_n_m=1000,
            panel_span_m=1,
        )
        assert tensioned["f0"] > untensioned["f0"]
        assert tensioned["tension_f0_hz"] > 0
        assert tensioned["assumptions"]

    def test_membrane_loss_factor_controls_q(self):
        low_loss = membrane_absorber(10, 0.1, loss_factor=0.05)
        high_loss = membrane_absorber(10, 0.1, loss_factor=0.25)
        assert low_loss["Q"] == pytest.approx(10)
        assert high_loss["Q"] == pytest.approx(2)


class TestRecommendedArea:
    def test_area_uses_governing_band_not_frequency_sum(self):
        result = recommended_absorber_area(
            {"125": 0.5, "250": 0.5, "500": 0.8},
            {"125": 5.0, "250": 2.0, "500": 8.0},
        )
        assert result["per_band_area_m2"]["125"] == pytest.approx(10)
        assert result["per_band_area_m2"]["500"] == pytest.approx(10)
        assert result["recommended_area_m2"] == pytest.approx(10)
        assert set(result["governing_bands"]) == {"125", "500"}

    def test_replacement_uses_net_coefficient_and_area_limit(self):
        added = recommended_absorber_area(
            {"500": 0.8}, {"500": 8}, installation_mode="added"
        )
        replacement = recommended_absorber_area(
            {"500": 0.8},
            {"500": 8},
            existing_surface_alpha={"500": 0.2},
            installation_mode="replacement",
            available_area_m2=12,
        )
        assert added["recommended_area_m2"] == pytest.approx(10)
        assert replacement["recommended_area_m2"] == pytest.approx(13.333, abs=0.001)
        assert replacement["feasible"] is False
        assert replacement["remaining_missing_absorption_m2_sabins"]["500"] > 0


class TestAbsorberAPI:
    def test_porous_endpoint(self, client, paid_headers):
        response = client.post("/api/v1/design/absorbers/porous", json={
            "thickness_m": 0.05, "flow_resistivity": 10000, "density_kgm3": 100,
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert "alpha" in data
        assert len(data["alpha"]) == 6

    def test_helmholtz_endpoint(self, client, paid_headers):
        response = client.post("/api/v1/design/absorbers/helmholtz", json={
            "neck_area_m2": 0.01, "cavity_volume_m3": 0.001, "neck_length_m": 0.1,
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["f0"] > 0

    def test_membrane_endpoint(self, client, paid_headers):
        response = client.post("/api/v1/design/absorbers/membrane", json={
            "mass_per_area_kgm2": 10, "air_gap_m": 0.1,
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["f0"] > 0

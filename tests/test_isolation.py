import pytest
from acoustic_core.isolation import (
    mass_law_tl, critical_frequency, single_panel_tl,
    msr_resonance, double_panel_tl,
    calculate_stc, calculate_rw,
    evaluate_nc, get_nc_target,
)


class TestMassLaw:
    def test_basic(self):
        tl = mass_law_tl(50, 500)
        assert tl > 20
        assert tl < 60

    def test_higher_mass_more_tl(self):
        tl1 = mass_law_tl(10, 500)
        tl2 = mass_law_tl(50, 500)
        assert tl2 > tl1

    def test_higher_freq_more_tl(self):
        tl1 = mass_law_tl(50, 125)
        tl2 = mass_law_tl(50, 4000)
        assert tl2 > tl1


class TestCriticalFrequency:
    def test_thicker_lower_fc(self):
        fc1 = critical_frequency(0.05)
        fc2 = critical_frequency(0.1)
        assert fc2 < fc1

    def test_valid(self):
        fc = critical_frequency(0.1)
        assert fc > 0
        assert fc != float('inf')


class TestSinglePanel:
    def test_returns_6_bands(self):
        tl = single_panel_tl(50, 0.1)
        assert len(tl) == 6

    def test_notch_at_fc(self):
        from acoustic_core.isolation import coincidence_notch
        notch = coincidence_notch(3000, 3000)
        assert notch > 5, f"Notch should be significant at fc, got {notch}"
        notch_off = coincidence_notch(100, 3000)
        assert notch_off < notch, "Notch should be smaller far from fc"


class TestDoublePanel:
    def test_returns_6_bands(self):
        tl = double_panel_tl(50, 50, 0.05)
        assert len(tl) == 6

    def test_resonance_f0(self):
        f0 = msr_resonance(50, 50, 0.05)
        assert f0 > 0

    def test_above_resonance_better_tl(self):
        tl = double_panel_tl(50, 50, 0.05)
        assert tl["4000"] > tl["125"]


class TestSTC:
    def test_basic(self):
        tl = {"125": 30, "250": 35, "500": 40, "1000": 45, "2000": 50, "4000": 55}
        result = calculate_stc(tl)
        assert "stc" in result
        assert result["stc"] >= 0


class TestRw:
    def test_basic(self):
        tl = {"125": 30, "250": 35, "500": 40, "1000": 45, "2000": 50, "4000": 55}
        result = calculate_rw(tl)
        assert "rw" in result


class TestNC:
    def test_evaluate(self):
        spl = {"125": 50, "250": 45, "500": 40, "1000": 35, "2000": 30, "4000": 25}
        result = evaluate_nc(spl)
        assert "nc" in result
        assert result["nc"] >= 0

    def test_targets(self):
        target = get_nc_target("estudio_grabacion")
        assert target is not None
        assert target["nc"] == 15

    def test_invalid_target(self):
        assert get_nc_target("no_existe") is None


class TestIsolationAPI:
    def test_single_panel(self, client):
        response = client.post("/api/v1/design/isolation/single-panel", json={
            "mass_per_area_kgm2": 50, "thickness_m": 0.1, "material_type": "concreto",
        })
        assert response.status_code == 200
        data = response.json()
        assert "tl" in data
        assert "fc_hz" in data
        assert "stc" in data
        assert "rw" in data

    def test_double_panel(self, client):
        response = client.post("/api/v1/design/isolation/double-panel", json={
            "m1_kgm2": 50, "m2_kgm2": 20, "gap_m": 0.1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "tl" in data
        assert "f0_hz" in data

    def test_nc(self, client):
        response = client.post("/api/v1/design/isolation/nc", json={
            "spl": {"125": 50, "250": 45, "500": 40, "1000": 35, "2000": 30, "4000": 25},
        })
        assert response.status_code == 200
        data = response.json()
        assert "nc" in data

    def test_nc_targets(self, client):
        response = client.get("/api/v1/design/isolation/nc-targets")
        assert response.status_code == 200
        data = response.json()
        assert "estudio_grabacion" in data

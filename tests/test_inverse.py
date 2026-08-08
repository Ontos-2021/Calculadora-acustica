import pytest
from acoustic_core.inverse import required_absorption, current_absorption, missing_absorption, suggest_materials, suggest_placement
from acoustic_core.models import Material, Surface, Room
from acoustic_core.presets import MATERIALES_PRESETS


class TestRequiredAbsorption:
    def test_basic(self):
        req = required_absorption(60, {"500": 0.5})
        assert req["500"] == pytest.approx(0.161 * 60 / 0.5, rel=0.01)

    def test_all_bands(self):
        req = required_absorption(100, {"125": 0.5, "250": 0.5, "500": 0.5, "1000": 0.5, "2000": 0.5, "4000": 0.5})
        assert len(req) == 6
        assert all(v > 0 for v in req.values())

    def test_zero_rt60(self):
        req = required_absorption(60, {"500": 0})
        assert req["500"] == float('inf')


class TestCurrentAbsorption:
    def test_basic(self, sala_basica):
        curr = current_absorption(sala_basica)
        assert len(curr) == 6
        assert all(v > 0 for v in curr.values())

    def test_all_concrete(self, sala_basica):
        curr = current_absorption(sala_basica)
        assert curr["500"] == pytest.approx(94 * 0.05, rel=0.01)


class TestMissingAbsorption:
    def test_needs_absorption(self, sala_basica):
        miss = missing_absorption(sala_basica, {"125": 0.3, "250": 0.3, "500": 0.3, "1000": 0.3, "2000": 0.3, "4000": 0.3})
        assert all(v >= 0 for v in miss.values())

    def test_already_compliant(self, sala_basica):
        miss = missing_absorption(sala_basica, {"125": 10, "250": 10, "500": 10, "1000": 10, "2000": 10, "4000": 10})
        assert all(v == 0 for v in miss.values())


class TestSuggestMaterials:
    def test_returns_suggestions(self, sala_basica):
        mats = suggest_materials(sala_basica, "home_studio")
        assert len(mats) > 0
        assert all("material" in m for m in mats)

    def test_suggestions_have_area(self, sala_basica):
        mats = suggest_materials(sala_basica, "home_studio")
        if mats:
            assert mats[0]["area_needed_m2"] > 0

    def test_high_absorption_room_needs_none(self):
        from acoustic_core.presets import MATERIALES_PRESETS
        lana = MATERIALES_PRESETS["Lana mineral (100mm)"]
        areas = [12, 12, 15, 15, 20, 20]
        room = Room(
            largo=5, ancho=4, alto=3,
            superficies=[Surface(nombre=f"S{i}", area=areas[i], material=lana) for i in range(6)],
        )
        mats = suggest_materials(room, "sala_conciertos")
        if mats:
            assert any("mensaje" in m for m in mats)


class TestSuggestPlacement:
    def test_returns_placements(self, sala_basica):
        placements = suggest_placement(sala_basica, "home_studio")
        assert len(placements) > 0
        assert all("surface" in p for p in placements)

    def test_uses_pressure_map(self, sala_basica):
        pmap = {"pressure": [[0.5] * 10 for _ in range(10)]}
        placements = suggest_placement(sala_basica, "home_studio", pmap)
        assert len(placements) > 0


class TestInverseAPI:
    def test_inverse_endpoint(self, client):
        response = client.post("/api/v1/design/inverse", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "target_uso": "home_studio",
        })
        assert response.status_code == 200
        data = response.json()
        assert "current_absorption" in data
        assert "required_absorption" in data
        assert "missing_absorption" in data
        assert "material_suggestions" in data

    def test_inverse_with_placement(self, client):
        response = client.post("/api/v1/design/inverse", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "target_uso": "home_studio",
            "include_placement": True,
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["placement_suggestions"]) > 0

    def test_invalid_uso(self, client):
        response = client.post("/api/v1/design/inverse", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "target_uso": "no_existe",
        })
        assert response.status_code == 400

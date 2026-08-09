import pytest
from acoustic_core.inverse import (
    current_absorption,
    design_treatment,
    missing_absorption,
    optimize_treatment,
    required_absorption,
    suggest_materials,
    suggest_placement,
    treatment_absorption_gain,
    verify_treatment_plan,
)
from acoustic_core.models import BANDAS_OCTAVA, Material, Room, Surface
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
            assert mats[0]["installation_mode"] == "replacement"
            assert mats[0]["governing_bands"]

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

    def test_different_boundary_maps_change_priority(self, sala_basica):
        front_hot = {"pressure": [[10, 1], [10, 1]]}
        rear_hot = {"pressure": [[1, 10], [1, 10]]}
        front = suggest_placement(sala_basica, "home_studio", front_hot)
        rear = suggest_placement(sala_basica, "home_studio", rear_hot)
        assert front[0]["surface_index"] == 0
        assert rear[0]["surface_index"] == 1
        assert front[0]["pressure_evidence"] != "no pressure evidence; neutral priorities"

    def test_explicit_surface_evidence_and_available_area(self, sala_basica):
        placements = suggest_placement(
            sala_basica,
            "home_studio",
            {"surface_scores": {"ceiling": 10, "floor": 1}},
            available_area_m2={"ceiling": 4},
        )
        assert len(placements) == 1
        assert placements[0]["surface_index"] == 5
        assert placements[0]["available_area_m2"] == pytest.approx(4)

    def test_placement_uses_governing_band_not_sabin_sum(self, sala_basica):
        target = {band: 0.3 for band in BANDAS_OCTAVA}
        missing = missing_absorption(sala_basica, target)
        placement = suggest_placement(sala_basica, "home_studio")[0]
        assert placement["missing_absorption_m2"] == pytest.approx(max(missing.values()))
        assert placement["missing_absorption_m2"] < sum(missing.values())


class TestTreatmentSemantics:
    def test_added_and_replacement_gain_are_distinct(self):
        treatment = Material(nombre="treatment", alpha_unico=0.8)
        substrate = Material(nombre="substrate", alpha_unico=0.2)
        added = treatment_absorption_gain(treatment, installation_mode="added")
        replacement = treatment_absorption_gain(
            treatment,
            existing_material=substrate,
            installation_mode="replacement",
        )
        assert all(added[band] == pytest.approx(0.8) for band in BANDAS_OCTAVA)
        assert all(replacement[band] == pytest.approx(0.6) for band in BANDAS_OCTAVA)

    def test_forward_verification_uses_net_replacement_gain(self, sala_basica):
        material = Material(nombre="uniform-50", alpha_unico=0.5)
        result = verify_treatment_plan(
            sala_basica,
            {band: 1.2 for band in BANDAS_OCTAVA},
            [{
                "material": material,
                "area_m2": 10,
                "surface_index": 0,
                "installation_mode": "replacement",
            }],
        )
        # Existing A=94*0.05=4.7; replacing 10 m2 adds 10*(0.5-0.05)=4.5.
        assert result["predicted_absorption_m2_sabins"]["500"] == pytest.approx(9.2)
        assert result["predicted_rt60_s"]["500"] == pytest.approx(
            0.161 * 60 / 9.2,
            abs=1e-4,
        )
        assert "not summed" in result["aggregation_rule"]

    def test_forward_verification_rejects_surface_overallocation(self, sala_basica):
        with pytest.raises(ValueError, match="exceeds surface"):
            verify_treatment_plan(
                sala_basica,
                {band: 1 for band in BANDAS_OCTAVA},
                [{
                    "material": "Panel fibra de vidrio (50mm)",
                    "area_m2": 12.1,
                    "surface_index": 0,
                    "installation_mode": "replacement",
                }],
            )


class TestTreatmentOptimization:
    def test_bounded_plan_is_forward_verified(self, sala_basica):
        result = optimize_treatment(
            sala_basica,
            {band: 0.5 for band in BANDAS_OCTAVA},
            candidate_materials=["Lana mineral (100mm)"],
            area_step_m2=0.25,
        )
        assert result["status"] == "feasible"
        assert result["all_bands_meet"] is True
        assert result["forward_verification"]["all_bands_meet"] is True
        for band in BANDAS_OCTAVA:
            assert result["predicted_rt60_s"][band] <= 0.5

    def test_available_area_constraint_reports_shortfall(self, sala_basica):
        result = optimize_treatment(
            sala_basica,
            {band: 0.5 for band in BANDAS_OCTAVA},
            candidate_materials=["Lana mineral (100mm)"],
            available_area_m2=5,
            area_step_m2=0.25,
        )
        assert result["status"] == "area_limited"
        assert result["used_area_m2"] <= 5
        assert result["all_bands_meet"] is False

    def test_complementary_material_combination(self, sala_basica):
        low_band = Material(
            nombre="low-band",
            alphas={
                "125": 0.9, "250": 0.9, "500": 0.1,
                "1000": 0.1, "2000": 0.1, "4000": 0.1,
            },
        )
        high_band = Material(
            nombre="high-band",
            alphas={
                "125": 0.1, "250": 0.1, "500": 0.9,
                "1000": 0.9, "2000": 0.9, "4000": 0.9,
            },
        )
        result = optimize_treatment(
            sala_basica,
            {band: 0.5 for band in BANDAS_OCTAVA},
            candidate_materials=[low_band, high_band],
            max_materials=2,
            area_step_m2=0.5,
        )
        assert set(result["selected_materials"]) == {"low-band", "high-band"}
        assert result["all_bands_meet"] is True

    def test_usage_wrapper_exposes_target(self, sala_basica):
        result = design_treatment(
            sala_basica,
            "sala_conferencias",
            candidate_materials=["Lana mineral (100mm)"],
            area_step_m2=1,
        )
        assert result["target_uso"] == "sala_conferencias"
        assert result["target_label"]


class TestInverseAPI:
    def test_inverse_endpoint(self, client, paid_headers):
        response = client.post("/api/v1/design/inverse", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "target_uso": "home_studio",
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert "current_absorption" in data
        assert "required_absorption" in data
        assert "missing_absorption" in data
        assert "material_suggestions" in data

    def test_inverse_with_placement(self, client, paid_headers):
        response = client.post("/api/v1/design/inverse", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "target_uso": "home_studio",
            "include_placement": True,
        }, headers=paid_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["placement_suggestions"]) > 0

    def test_invalid_uso(self, client, paid_headers):
        response = client.post("/api/v1/design/inverse", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "target_uso": "no_existe",
        }, headers=paid_headers)
        assert response.status_code == 400

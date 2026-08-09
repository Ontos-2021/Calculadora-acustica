import math

import pytest
from acoustic_core.presets import (
    AIR_ABSORPTION_DEFAULT,
    CATEGORIAS,
    MATERIAL_CATALOG_METADATA,
    MATERIALES_PRESETS,
    AudienceConfig,
    audience_absorption_result,
    calculate_air_absorption,
    calculate_air_attenuation,
    calculate_audience_absorption,
    classify_iso11654,
    get_material_metadata,
    iso11654_diagnostics,
    material_catalog_records,
    search_materials,
)


class TestPresets:
    def test_material_count(self):
        assert len(MATERIALES_PRESETS) >= 38

    def test_categories_count(self):
        assert len(CATEGORIAS) >= 8

    def test_all_have_valid_alphas(self):
        for name, mat in MATERIALES_PRESETS.items():
            for banda in ["125", "250", "500", "1000", "2000", "4000"]:
                assert 0 <= mat.alphas.get(banda, 0) <= 1, f"{name}: bad alpha at {banda}"

    def test_backward_compat_names(self):
        for old in ["Concreto", "Madera", "Yeso", "Vidrio", "Alfombra gruesa", "Cortina pesada", "Panel acústico", "Espuma acústica"]:
            assert old in MATERIALES_PRESETS, f"Missing backward compat: {old}"

    def test_backward_compat_values_match(self):
        assert MATERIALES_PRESETS["Concreto"].alphas == MATERIALES_PRESETS["Concreto sin pintar"].alphas
        assert MATERIALES_PRESETS["Madera"].alphas == MATERIALES_PRESETS["Madera contrachapada (10mm)"].alphas

    def test_alpha_w_computed(self):
        mat = MATERIALES_PRESETS["Panel fibra de vidrio (50mm)"]
        assert mat.alpha_w is not None
        assert 0 <= mat.alpha_w <= 1

    def test_material_has_categoria(self):
        for name, mat in MATERIALES_PRESETS.items():
            assert mat.categoria, f"{name} has no categoria"

    def test_catalog_metadata_is_parallel_and_transparent(self):
        assert set(MATERIAL_CATALOG_METADATA) == set(MATERIALES_PRESETS)
        for name, material in MATERIALES_PRESETS.items():
            record = get_material_metadata(name)
            assert record.mounting_condition
            assert record.data_status == "engineering_estimate_not_product_test"
            assert "not" in record.provenance.lower()
            assert record.uncertainty.expanded > 0
            assert material.provenance == record.provenance
            assert material.uncertainty == record.uncertainty

    def test_catalog_helper_can_exclude_compatibility_aliases(self):
        canonical = material_catalog_records(include_aliases=False)
        assert len(canonical) == len(MATERIALES_PRESETS) - 8
        assert all(record["alias_of"] is None for record in canonical)

    def test_search_by_category(self):
        results = search_materials(categoria="Espumas")
        assert len(results) >= 2
        assert all(m.categoria == "Espumas" for m in results)

    def test_search_by_query(self):
        results = search_materials(query="vidrio")
        assert len(results) >= 1
        assert all("vidrio" in m.nombre.lower() for m in results)

    def test_search_by_alpha_w_range(self):
        results = search_materials(min_alpha_w=0.8)
        assert len(results) >= 1
        assert all(m.alpha_w is not None and m.alpha_w >= 0.8 for m in results)

    def test_search_no_results(self):
        results = search_materials(query="zzz_no_existe")
        assert len(results) == 0


class TestISO11654:
    def test_class_a(self):
        w, cls = classify_iso11654({"250": 0.95, "500": 0.95, "1000": 0.95, "2000": 0.95})
        assert w >= 0.90
        assert cls == "A"

    def test_class_b(self):
        w, cls = classify_iso11654({"250": 0.85, "500": 0.85, "1000": 0.85, "2000": 0.85})
        assert 0.80 <= w < 0.90
        assert cls == "B"

    def test_class_c(self):
        w, cls = classify_iso11654({"250": 0.65, "500": 0.65, "1000": 0.65, "2000": 0.65})
        assert 0.60 <= w < 0.80
        assert cls == "C"

    def test_class_d(self):
        w, cls = classify_iso11654({"250": 0.40, "500": 0.40, "1000": 0.40, "2000": 0.40})
        assert 0.30 <= w < 0.60
        assert cls == "D"

    def test_class_e(self):
        w, cls = classify_iso11654({"250": 0.20, "500": 0.20, "1000": 0.20, "2000": 0.20})
        assert 0.15 <= w < 0.30
        assert cls == "E"

    def test_no_classified(self):
        w, cls = classify_iso11654({"250": 0.02, "500": 0.02, "1000": 0.02, "2000": 0.02})
        assert w < 0.15
        assert cls == "No clasificado"

    def test_rounding(self):
        w1, _ = classify_iso11654({"250": 0.32, "500": 0.33, "1000": 0.31, "2000": 0.32})
        # At 0.35 the three unfavorable deviations total 0.09, so the public
        # reference-curve rule accepts 0.35 even though the arithmetic mean does not.
        assert w1 == pytest.approx(0.35)

    def test_public_reference_curve_example_and_shape_indicators(self):
        result = iso11654_diagnostics({
            "250": 0.35,
            "500": 0.60,
            "1000": 0.85,
            "2000": 0.90,
            "4000": 0.90,
        })
        assert result.alpha_w == pytest.approx(0.60)
        assert result.iso_class == "C"
        assert result.shifted_reference_curve == {
            "250": 0.40,
            "500": 0.60,
            "1000": 0.60,
            "2000": 0.60,
            "4000": 0.50,
        }
        assert result.unfavorable_deviation_sum == pytest.approx(0.05)
        assert result.shape_indicators == ("M", "H")
        assert result.designation == "alpha_w = 0.60 (MH)"
        assert "not" in result.implementation_note.lower()

    def test_unfavorable_deviation_limit_is_inclusive(self):
        result = iso11654_diagnostics({
            "250": 0.55,
            "500": 0.75,
            "1000": 0.80,
            "2000": 0.80,
            "4000": 0.80,
        })
        assert result.alpha_w == pytest.approx(0.80)
        assert result.unfavorable_deviation_sum == pytest.approx(0.10)

    def test_diagnostics_requires_all_five_practical_coefficients(self):
        with pytest.raises(ValueError, match="4000 Hz"):
            iso11654_diagnostics({
                "250": 0.5, "500": 0.5, "1000": 0.5, "2000": 0.5,
            })

    def test_legacy_wrapper_discloses_inferred_4000_in_diagnostics(self):
        result = iso11654_diagnostics(
            {"250": 0.5, "500": 0.5, "1000": 0.5, "2000": 0.5},
            allow_legacy_4000_inference=True,
        )
        assert result.inferred_bands == ("4000",)


class TestAirAbsorption:
    def test_positive_coefficient(self):
        m = calculate_air_absorption(1000, 50, 20)
        assert m > 0

    def test_increases_with_frequency(self):
        m125 = calculate_air_absorption(125, 50, 20)
        m4k = calculate_air_absorption(4000, 50, 20)
        assert m4k > m125

    def test_default_values(self):
        assert len(AIR_ABSORPTION_DEFAULT) == 6
        for b, v in AIR_ABSORPTION_DEFAULT.items():
            assert v > 0

    @pytest.mark.parametrize("humidity", [0.0, 100.0])
    def test_humidity_endpoints_are_finite(self, humidity):
        result = calculate_air_attenuation(4000, humidity, 20, distance_m=10)
        assert math.isfinite(result.attenuation_db_per_m)
        assert result.attenuation_db_per_m > 0
        assert 0 < result.energy_ratio <= 1

    def test_api_friendly_result_has_consistent_units(self):
        result = calculate_air_attenuation(1000, 50, 20, distance_m=25)
        assert result.attenuation_db == pytest.approx(
            result.attenuation_db_per_m * 25
        )
        assert result.energy_decay_m_inv == pytest.approx(
            2 * result.amplitude_attenuation_np_per_m
        )
        assert calculate_air_absorption(1000, 50, 20) == pytest.approx(
            result.energy_decay_m_inv
        )

    def test_invalid_humidity_is_rejected(self):
        with pytest.raises(ValueError, match="between 0 and 100"):
            calculate_air_attenuation(1000, 100.1, 20)


class TestAudienceAbsorption:
    def test_zero_people(self):
        result = calculate_audience_absorption(AudienceConfig(num_people=0))
        assert all(v == 0 for v in result.values())

    def test_ten_people(self):
        result = calculate_audience_absorption(AudienceConfig(num_people=10))
        assert all(v > 0 for v in result.values())
        assert len(result) == 6

    def test_values_decrease_at_low_freq(self):
        result = calculate_audience_absorption(AudienceConfig(num_people=10))
        assert result["125"] < result["500"]

    def test_standing_less_absorption(self):
        seated = calculate_audience_absorption(AudienceConfig(num_people=10, seated=True))
        standing = calculate_audience_absorption(AudienceConfig(num_people=10, seated=False))
        for b in ["125", "250", "500"]:
            assert standing[b] < seated[b], f"Standing should absorb less at {b} Hz"

    def test_upholstery_and_occupancy_change_seated_load(self):
        upholstered = calculate_audience_absorption(
            AudienceConfig(num_people=100, seated=True, upholstered=True, occupied=0.5)
        )
        hard = calculate_audience_absorption(
            AudienceConfig(num_people=100, seated=True, upholstered=False, occupied=0.5)
        )
        full = calculate_audience_absorption(
            AudienceConfig(num_people=100, seated=True, upholstered=True, occupied=1.0)
        )
        assert all(upholstered[band] > hard[band] for band in upholstered)
        assert all(full[band] > upholstered[band] for band in full)

    def test_detailed_audience_result_exposes_units_and_assumptions(self):
        result = audience_absorption_result(
            AudienceConfig(num_people=20, seated=True, upholstered=False, occupied=0.75)
        )
        assert result.occupied_people_equivalent == 15
        assert result.empty_seats_equivalent == 5
        assert result.assumptions
        assert "estimate" in result.estimate_label

    def test_invalid_occupancy_rejected(self):
        with pytest.raises(ValueError, match="between 0 and 1"):
            AudienceConfig(num_people=10, occupied=1.1)

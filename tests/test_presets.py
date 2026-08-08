import pytest
from acoustic_core.presets import (
    MATERIALES_PRESETS, CATEGORIAS, search_materials,
    classify_iso11654, calculate_air_absorption,
    AudienceConfig, calculate_audience_absorption,
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
        assert abs(w1 - 0.30) < 1e-10


class TestAirAbsorption:
    def test_positive_coefficient(self):
        m = calculate_air_absorption(1000, 50, 20)
        assert m > 0

    def test_increases_with_frequency(self):
        m125 = calculate_air_absorption(125, 50, 20)
        m4k = calculate_air_absorption(4000, 50, 20)
        assert m4k > m125

    def test_default_values(self):
        from acoustic_core.presets import AIR_ABSORPTION_DEFAULT
        assert len(AIR_ABSORPTION_DEFAULT) == 6
        for b, v in AIR_ABSORPTION_DEFAULT.items():
            assert v > 0


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

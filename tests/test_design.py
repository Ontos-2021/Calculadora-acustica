import math

import pytest

from acoustic_core.design import (
    DIMENSION_CONVENTION,
    PROPORCIONES,
    RT60_OBJETIVOS,
    bolt_area_distance,
    evaluate_bolt_area,
    find_closest_ratio,
    get_rt60_target,
    is_in_bolt_area,
)


class TestReferenceProportions:
    def test_exact_reference_has_zero_distance(self):
        result = find_closest_ratio(1.0, 1.25, 1.60)
        assert result["mas_cercana"] == "Golden Ratio"
        assert result["error"] == pytest.approx(0.0)

    def test_comparison_uses_unrounded_ratios(self):
        dimensions = (3.0, 3.421, 4.199)
        normalized = (1.0, dimensions[1] / dimensions[0], dimensions[2] / dimensions[0])
        expected = min(
            (
                abs(normalized[1] - ratio[1]) + abs(normalized[2] - ratio[2]),
                name,
            )
            for name, ratio in PROPORCIONES.items()
        )
        result = find_closest_ratio(*dimensions)
        assert result["mas_cercana"] == expected[1]
        assert result["error"] == pytest.approx(expected[0], rel=1e-15)
        assert result["proporcion_actual"] == pytest.approx(normalized)

    def test_all_reference_ratios_remain_available(self):
        result = find_closest_ratio(5, 4, 3)
        assert len(result["todas"]) == len(PROPORCIONES) == 5

    def test_dimension_convention_is_explicit_and_orientation_independent(self):
        first = find_closest_ratio(8, 5, 3)
        second = find_closest_ratio(3, 8, 5)
        assert first["proporcion_actual"] == second["proporcion_actual"]
        assert first["convencion_dimensiones"] == DIMENSION_CONVENTION

    def test_integer_multiple_is_reported_regardless_of_argument_order(self):
        result = find_closest_ratio(2, 5, 4)
        assert ("alto", "largo", 2) in result["multiplos_enteros"]


class TestBoltArea:
    def test_canonical_bolt_ratio_is_inside(self):
        result = evaluate_bolt_area(1.0, 1.4, 1.9)
        assert result.is_inside
        assert result.distance == 0.0
        assert is_in_bolt_area(1.4, 1.9)
        assert bolt_area_distance(1.4, 1.9) == 0.0

    def test_cube_distance_matches_nearest_area_corner(self):
        result = evaluate_bolt_area(1.0, 1.0, 1.0)
        assert not result.is_inside
        assert result.nearest_ratio == (1.0, 1.1, 1.4)
        assert result.distance == pytest.approx(math.hypot(0.1, 0.4))

    def test_membership_and_distance_are_scale_invariant(self):
        first = evaluate_bolt_area(1.0, 1.4, 1.9)
        scaled = evaluate_bolt_area(3.0, 4.2, 5.7)
        assert first.is_inside == scaled.is_inside
        assert first.distance == pytest.approx(scaled.distance)
        assert first.normalized_ratio == pytest.approx(scaled.normalized_ratio)
        assert first.nearest_ratio == pytest.approx(scaled.nearest_ratio)

    def test_boundary_is_inclusive(self):
        assert is_in_bolt_area(1.1, 1.4)
        assert is_in_bolt_area(1.9, 2.8)

    def test_invalid_dimension_is_rejected(self):
        with pytest.raises(ValueError):
            evaluate_bolt_area(0, 4, 5)


class TestRT60Target:
    def test_valid_use(self):
        target = get_rt60_target("home_studio")
        assert target is not None
        assert target["valores"]["500"] == pytest.approx(0.30)

    def test_invalid_use(self):
        assert get_rt60_target("uso_inexistente") is None

    def test_every_target_has_complete_octave_set(self):
        assert all(len(data["valores"]) == 6 for data in RT60_OBJETIVOS.values())

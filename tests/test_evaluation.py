import math

import pytest

from acoustic_core.evaluation import (
    assess_diffuse_field,
    calculate_modal_bandwidth,
    calculate_schroeder,
    evaluate_bonello,
    find_degenerate_dimensions,
    get_mode_distribution,
)
from acoustic_core.models import Mode, ModeType
from acoustic_core.resonance import calculate_modes, detect_overlapping_modes
from acoustic_core.spectrum import THIRD_OCTAVE_BANDS


def _mode(frequency: float, index: int) -> Mode:
    return Mode(
        indices=[index + 1, 0, 0],
        frecuencia=frequency,
        tipo=ModeType.AXIAL,
        peso_db=0.0,
    )


class TestTransitionMetrics:
    def test_schroeder_reference_formula_is_full_precision(self):
        expected = 2000.0 * math.sqrt(0.5 / 60.0)
        result = calculate_schroeder(0.5, 60.0)
        assert result == pytest.approx(expected, rel=1e-15)
        assert result != round(result, 1)

    def test_modal_bandwidth_reference_formula_is_full_precision(self):
        assert calculate_modal_bandwidth(0.7) == pytest.approx(2.2 / 0.7, rel=1e-15)

    @pytest.mark.parametrize("rt60, volume", [(0, 60), (-1, 60), (0.5, 0)])
    def test_non_physical_transition_input_returns_zero(self, rt60, volume):
        assert calculate_schroeder(rt60, volume) == 0.0

    def test_non_finite_input_is_rejected(self):
        with pytest.raises(ValueError):
            calculate_schroeder(math.inf, 60)
        with pytest.raises(ValueError):
            calculate_modal_bandwidth(math.nan)


class TestBonello:
    def test_exact_upper_edge_belongs_to_next_band(self):
        _, upper_1000 = THIRD_OCTAVE_BANDS.edges(1000.0)
        result = evaluate_bonello([upper_1000 - 1e-9, upper_1000])
        assert result["bandas"][1000.0] == 1
        assert result["bandas"][1250.0] == 1
        assert result["total_modos"] == 2

    def test_non_decreasing_counts_pass_explicit_criterion(self):
        frequencies = [
            exact
            for nominal, exact in zip(
                THIRD_OCTAVE_BANDS.centers_hz,
                THIRD_OCTAVE_BANDS.exact_centers_hz,
            )
            if nominal < 500.0
        ]
        result = evaluate_bonello(frequencies)
        assert result["cumple"]
        assert result["violaciones"] == []
        assert all(count == 1 for count in result["bandas"].values())

    def test_decreasing_count_reports_band_index(self):
        first = THIRD_OCTAVE_BANDS.exact_centers_hz[0]
        second = THIRD_OCTAVE_BANDS.exact_centers_hz[1]
        result = evaluate_bonello([first, first, second])
        assert not result["cumple"]
        assert 1 in result["violaciones"]

    def test_empty_bands_between_occupied_bands_are_not_skipped(self):
        center_400 = THIRD_OCTAVE_BANDS.exact_centers_hz[
            THIRD_OCTAVE_BANDS.index(400.0)
        ]
        center_630 = THIRD_OCTAVE_BANDS.exact_centers_hz[
            THIRD_OCTAVE_BANDS.index(630.0)
        ]
        result = evaluate_bonello([center_400, center_400, center_630])
        assert result["bandas"][500.0] == 0
        assert result["bandas"][630.0] == 1
        assert not result["cumple"]

    def test_cube_fails_modal_distribution(self, sala_cubica):
        frequencies = [mode.frecuencia for mode in calculate_modes(sala_cubica)]
        assert not evaluate_bonello(frequencies)["cumple"]

    def test_invalid_frequency_is_rejected(self):
        with pytest.raises(ValueError):
            evaluate_bonello([math.nan])


class TestDimensionDegeneracy:
    def test_equal_dimensions(self):
        warnings = find_degenerate_dimensions(3, 3, 4)
        assert any("iguales" in warning for warning in warnings)

    def test_integer_multiples_are_detected_in_both_argument_directions(self):
        warnings = find_degenerate_dimensions(2, 5, 4)
        assert any("Alto es múltiplo entero de Largo (2x)" in warning for warning in warnings)

    def test_non_integer_dimensions_have_no_ratio_warning(self):
        warnings = find_degenerate_dimensions(5, 4, 3)
        assert not [
            warning
            for warning in warnings
            if "iguales" in warning or "múltiplo" in warning
        ]


class TestDiffuseField:
    def test_overlap_of_three_meets_diffuse_threshold(self):
        modes = [_mode(100, 0), _mode(100.5, 1), _mode(101, 2), _mode(110, 3)]
        detect_overlapping_modes(modes, 1.0)
        assessment = assess_diffuse_field(modes)
        assert assessment["campo_difuso"]
        assert assessment["solapamiento_maximo"] == 3
        assert len(assessment["clusters_difusos"]) == 1

    def test_pair_only_does_not_meet_threshold(self):
        modes = detect_overlapping_modes([_mode(100, 0), _mode(101, 1)], 1.0)
        assert not assess_diffuse_field(modes)["is_diffuse"]

    def test_distribution_counts_all_modal_types(self, sala_basica):
        modes = calculate_modes(sala_basica)
        distribution = get_mode_distribution(modes)
        total = sum(distribution[key] for key in ("axiales", "tangenciales", "oblicuos"))
        assert total == len(modes)

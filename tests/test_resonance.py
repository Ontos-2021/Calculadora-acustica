import math

import pytest

from acoustic_core.environment import Environment
from acoustic_core.models import Mode, ModeType
from acoustic_core.resonance import (
    calculate_modes,
    classify_mode,
    detect_degenerate_modes,
    detect_overlapping_modes,
)


def _mode(frequency: float, index: int) -> Mode:
    return Mode(
        indices=[index + 1, 0, 0],
        frecuencia=frequency,
        tipo=ModeType.AXIAL,
        peso_db=0.0,
    )


class TestClassifyMode:
    @pytest.mark.parametrize(
        ("indices", "expected_type", "expected_weight"),
        [
            ((2, 0, 0), ModeType.AXIAL, 0.0),
            ((1, 1, 0), ModeType.TANGENTIAL, -3.0),
            ((1, 1, 1), ModeType.OBLIQUE, -6.0),
        ],
    )
    def test_classification_and_energy_weight(self, indices, expected_type, expected_weight):
        mode_type, weight = classify_mode(*indices)
        assert mode_type == expected_type
        assert weight == expected_weight

    def test_zero_tuple_is_not_a_mode(self):
        with pytest.raises(ValueError, match="not a physical"):
            classify_mode(0, 0, 0)


class TestCalculateModes:
    def test_default_preserves_historical_order_bound(self, sala_basica):
        modes = calculate_modes(sala_basica)
        assert len(modes) == 5**3 - 1
        assert max(max(mode.indices) for mode in modes) == 4

    def test_explicit_max_order_is_inclusive(self, sala_basica):
        modes = calculate_modes(sala_basica, max_order=1)
        assert len(modes) == 2**3 - 1
        assert {tuple(mode.indices) for mode in modes} == {
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (1, 1, 0),
            (1, 0, 1),
            (0, 1, 1),
            (1, 1, 1),
        }

    def test_axial_frequency_matches_closed_form_without_rounding(self, sala_basica):
        modes = calculate_modes(sala_basica, max_order=1, c=340.0)
        axial_x = next(mode for mode in modes if mode.indices == [1, 0, 0])
        assert axial_x.frecuencia == pytest.approx(340.0 / (2.0 * sala_basica.largo))
        axial_z = next(mode for mode in modes if mode.indices == [0, 0, 1])
        expected = 340.0 / (2.0 * sala_basica.alto)
        assert axial_z.frecuencia == pytest.approx(expected)
        assert axial_z.frecuencia != round(axial_z.frecuencia, 1)

    def test_frequency_bounded_enumeration_is_complete(self, sala_basica):
        modes = calculate_modes(sala_basica, f_max=60.0, c=340.0)
        assert {tuple(mode.indices) for mode in modes} == {
            (1, 0, 0),
            (0, 1, 0),
            (0, 0, 1),
            (1, 1, 0),
        }
        assert all(mode.frecuencia <= 60.0 for mode in modes)

    def test_environment_controls_sound_speed(self, sala_basica):
        cold = calculate_modes(
            sala_basica,
            max_order=1,
            environment=Environment(temperature_c=0, relative_humidity=0),
        )
        warm = calculate_modes(
            sala_basica,
            max_order=1,
            environment=Environment(temperature_c=30, relative_humidity=0),
        )
        assert cold[0].frecuencia < warm[0].frecuencia

    def test_modes_are_sorted_and_classified(self, sala_basica):
        modes = calculate_modes(sala_basica)
        assert [mode.frecuencia for mode in modes] == sorted(mode.frecuencia for mode in modes)
        assert {mode.tipo for mode in modes} == set(ModeType)

    def test_bounds_are_mutually_exclusive(self, sala_basica):
        with pytest.raises(ValueError, match="either"):
            calculate_modes(sala_basica, max_order=2, f_max=100)


class TestDegenerate:
    def test_tolerance_is_applied_to_raw_frequency(self):
        modes = [_mode(100.0, 0), _mode(100.05, 1), _mode(101.0, 2)]
        detect_degenerate_modes(modes, tolerance=0.01)
        assert not any(mode.degenerado for mode in modes)

        detect_degenerate_modes(modes, tolerance=0.05)
        assert [mode.degenerado for mode in modes] == [True, True, False]
        assert [mode.multiplicity for mode in modes] == [2, 2, 1]
        assert modes[0].degeneracy_cluster == modes[1].degeneracy_cluster

    def test_cube_has_exact_permutation_degeneracy(self, sala_cubica):
        modes = detect_degenerate_modes(calculate_modes(sala_cubica), tolerance=1e-9)
        fundamentals = [mode for mode in modes if sum(mode.indices) == 1]
        assert len(fundamentals) == 3
        assert all(mode.degenerado and mode.multiplicity == 3 for mode in fundamentals)


class TestOverlapping:
    def test_connected_overlap_cluster_and_inclusive_bandwidth(self):
        modes = [_mode(100.0, 0), _mode(101.0, 1), _mode(102.0, 2), _mode(110.0, 3)]
        detect_overlapping_modes(modes, delta_f=2.0)
        assert [mode.solapado for mode in modes] == [True, True, True, False]
        assert [mode.overlap_multiplicity for mode in modes] == [3, 3, 3, 1]
        assert len({mode.overlap_cluster for mode in modes[:3]}) == 1

    def test_connected_chain_does_not_overstate_simultaneous_multiplicity(self):
        modes = [_mode(100.0, 0), _mode(102.0, 1), _mode(104.0, 2)]
        detect_overlapping_modes(modes, delta_f=2.0)
        assert len({mode.overlap_cluster for mode in modes}) == 1
        assert [mode.overlap_multiplicity for mode in modes] == [2, 2, 2]

    def test_invalid_tolerances_are_rejected(self):
        with pytest.raises(ValueError):
            detect_degenerate_modes([], tolerance=math.nan)
        with pytest.raises(ValueError):
            detect_overlapping_modes([], delta_f=-1)

import math

import pytest

from acoustic_core.models import Material, Mode, ModeType, Room, Surface
from acoustic_core.pressure import (
    compute_pressure_map,
    compute_single_mode_grid,
    find_optimal_listening,
    mode_pressure_at,
    spectral_levels_db_at,
)


MATERIAL = Material(nombre="Concrete", alpha_unico=0.1)
SURFACES = [
    Surface(nombre=name, area=area, material=MATERIAL)
    for name, area in zip(
        ("Front", "Back", "Left", "Right", "Floor", "Ceiling"),
        (12, 12, 15, 15, 20, 20),
    )
]


def _room(largo=5.0, ancho=4.0, alto=3.0):
    return Room(largo=largo, ancho=ancho, alto=alto, superficies=SURFACES)


def _mode(indices, frequency, weight_db=0.0):
    nonzero = sum(index > 0 for index in indices)
    mode_type = {
        1: ModeType.AXIAL,
        2: ModeType.TANGENTIAL,
        3: ModeType.OBLIQUE,
    }[nonzero]
    return Mode(
        indices=list(indices),
        frecuencia=frequency,
        tipo=mode_type,
        peso_db=weight_db,
    )


class TestSingleModePressure:
    def test_axial_mode_has_analytic_sign_and_node(self):
        room = _room()
        assert mode_pressure_at(room, 1, 0, 0, 0, 2, 1.2) == pytest.approx(1.0)
        assert mode_pressure_at(room, 1, 0, 0, 2.5, 2, 1.2) == pytest.approx(0.0, abs=1e-15)
        assert mode_pressure_at(room, 1, 0, 0, 5, 2, 1.2) == pytest.approx(-1.0)
        assert mode_pressure_at(room, 1, 0, 0, 5, 2, 1.2, magnitude=True) == pytest.approx(1.0)

    def test_grid_distinguishes_signed_pressure_and_magnitude(self):
        result = compute_single_mode_grid(_room(), 1, 0, 0, grid_size=3)
        assert result["pressure"] is result["signed_pressure"]
        assert result["quantity"] == "signed_normalized_pressure"
        assert result["signed_pressure"][0] == pytest.approx([1.0, 0.0, -1.0], abs=1e-15)
        assert result["magnitude"][0] == pytest.approx([1.0, 0.0, 1.0], abs=1e-15)

    @pytest.mark.parametrize(
        "args",
        [
            ((0, 0, 0), (1, 1, 1)),
            ((1, 0, 0), (-0.1, 1, 1)),
            ((1, 0, 0), (1, 4.1, 1)),
            ((1, 0, 0), (1, 1, 3.1)),
        ],
    )
    def test_indices_and_coordinates_are_validated(self, args):
        indices, coordinates = args
        with pytest.raises(ValueError):
            mode_pressure_at(_room(), *indices, *coordinates)


class TestAccumulatedPressure:
    def test_energy_weights_are_applied_before_normalization(self):
        room = _room()
        modes = [
            _mode((1, 0, 0), 50.0, 0.0),
            _mode((0, 1, 0), 60.0, -6.0),
        ]
        result = compute_pressure_map(room, modos=modes, max_freq=100, grid_size=3)
        weak_energy = 10.0 ** (-6.0 / 10.0)
        expected_midpoint_energy = weak_energy / (1.0 + weak_energy)
        assert result["energy"][0][1] == pytest.approx(expected_midpoint_energy, abs=1e-15)
        assert result["magnitude"][0][1] == pytest.approx(math.sqrt(expected_midpoint_energy))
        assert result["signed_pressure"] is None
        assert result["pressure"] is result["magnitude"]

    def test_grid_shape_and_normalization(self):
        result = compute_pressure_map(_room(), max_freq=120, grid_size=12)
        assert len(result["grid_x"]) == 12
        assert len(result["grid_y"]) == 12
        flat = [value for row in result["pressure"] for value in row]
        assert max(flat) == pytest.approx(1.0)
        assert min(flat) >= 0.0

    def test_no_mode_below_cutoff_returns_finite_zero_map(self):
        result = compute_pressure_map(_room(), max_freq=10, grid_size=4)
        assert result["num_modos"] == 0
        assert all(value == 0.0 for row in result["pressure"] for value in row)
        assert result["warnings"]

    def test_explicit_sound_speed_reaches_frequency_enumerator(self):
        slow = compute_pressure_map(_room(), max_freq=35, grid_size=3, c=300.0)
        fast = compute_pressure_map(_room(), max_freq=35, grid_size=3, c=400.0)
        assert slow["num_modos"] == 1
        assert fast["num_modos"] == 0

    def test_invalid_ear_height_and_grid_are_rejected(self):
        with pytest.raises(ValueError, match="ear_height"):
            compute_pressure_map(_room(), ear_height=3.1)
        with pytest.raises(ValueError, match="grid_size"):
            compute_pressure_map(_room(), grid_size=1)


class TestSpectralListeningOptimization:
    def test_spectral_levels_include_modal_db_weight(self):
        room = _room()
        modes = [
            _mode((1, 0, 0), 50.0, 0.0),
            _mode((0, 1, 0), 60.0, -3.0),
            _mode((0, 0, 1), 70.0, -6.0),
        ]
        levels = spectral_levels_db_at(room, modes, 0, 0, 0)
        assert levels == pytest.approx([0.0, -3.0, -6.0], abs=1e-14)

    def test_optimum_respects_physical_boundary_margin(self):
        result = find_optimal_listening(
            _room(),
            max_freq=150,
            grid_size=12,
            boundary_margin=0.4,
        )
        assert 0.4 <= result["x"] <= 4.6
        assert 0.4 <= result["y"] <= 3.6
        assert result["score"] >= 0.0
        assert result["score_unit"] == "dB standard deviation"

    def test_reports_movement_and_db_improvement_from_reference(self):
        current = (1.5, 2.0)
        result = find_optimal_listening(
            _room(),
            max_freq=150,
            grid_size=12,
            boundary_margin=0.3,
            current_position=current,
        )
        expected_movement = math.hypot(result["x"] - current[0], result["y"] - current[1])
        assert result["movement_m"] == pytest.approx(expected_movement)
        assert result["movement"]["distance_m"] == pytest.approx(expected_movement)
        assert result["improvement_db"] == pytest.approx(result["db_improvement"])
        assert result["improvement_db"] >= 0.0
        assert result["score"] <= result["reference_score_db"] + 1e-12

    def test_reference_must_respect_margin(self):
        with pytest.raises(ValueError, match="boundary_margin"):
            find_optimal_listening(
                _room(),
                grid_size=5,
                boundary_margin=0.5,
                current_position=(0.1, 2.0),
            )

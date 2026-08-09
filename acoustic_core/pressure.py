"""Analytic rigid-wall modal pressure maps and listening-position search."""

from __future__ import annotations

import math
from typing import Optional

from .environment import Environment
from .models import Mode, Room
from .resonance import calculate_modes


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _validate_indices(nx: int, ny: int, nz: int) -> None:
    indices = (nx, ny, nz)
    if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in indices):
        raise ValueError("modal indices must be non-negative integers")
    if indices == (0, 0, 0):
        raise ValueError("(0, 0, 0) is not a physical room mode")


def _validate_coordinate(value: float, upper: float, name: str) -> float:
    coordinate = _finite(value, name)
    if not 0.0 <= coordinate <= upper:
        raise ValueError(f"{name} must be within [0, {upper:g}] m")
    return coordinate


def _validate_grid_size(grid_size: int) -> None:
    if isinstance(grid_size, bool) or not isinstance(grid_size, int) or grid_size < 2:
        raise ValueError("grid_size must be an integer of at least two")


def _mode_pressure_value(
    nx: int,
    ny: int,
    nz: int,
    x: float,
    y: float,
    z: float,
    largo: float,
    ancho: float,
    alto: float,
) -> float:
    return (
        math.cos(nx * math.pi * x / largo)
        * math.cos(ny * math.pi * y / ancho)
        * math.cos(nz * math.pi * z / alto)
    )


def _mode_pressure_at(
    nx: int,
    ny: int,
    nz: int,
    x: float,
    y: float,
    z: float,
    largo: float,
    ancho: float,
    alto: float,
) -> float:
    """Return signed normalized modal pressure after validating the point."""

    _validate_indices(nx, ny, nz)
    dimensions = tuple(
        _finite(value, name)
        for value, name in ((largo, "largo"), (ancho, "ancho"), (alto, "alto"))
    )
    if any(value <= 0.0 for value in dimensions):
        raise ValueError("room dimensions must be positive")
    x = _validate_coordinate(x, dimensions[0], "x")
    y = _validate_coordinate(y, dimensions[1], "y")
    z = _validate_coordinate(z, dimensions[2], "z")
    return _mode_pressure_value(nx, ny, nz, x, y, z, *dimensions)


def mode_pressure_at(
    room: Room,
    nx: int,
    ny: int,
    nz: int,
    x: float,
    y: float,
    z: float,
    *,
    magnitude: bool = False,
) -> float:
    """Public point evaluator; signed pressure is the default quantity."""

    pressure = _mode_pressure_at(
        nx,
        ny,
        nz,
        x,
        y,
        z,
        room.largo,
        room.ancho,
        room.alto,
    )
    return abs(pressure) if magnitude else pressure


def _axis_grid(length: float, grid_size: int, margin: float = 0.0) -> list[float]:
    span = length - 2.0 * margin
    values = [margin + index * span / (grid_size - 1) for index in range(grid_size)]
    values[0] = margin
    values[-1] = length - margin
    return values


def compute_single_mode_grid(
    room: Room,
    nx: int,
    ny: int,
    nz: int,
    ear_height: float = 1.2,
    grid_size: int = 100,
) -> dict:
    _validate_indices(nx, ny, nz)
    _validate_grid_size(grid_size)
    ear_height = _validate_coordinate(ear_height, room.alto, "ear_height")
    x_vals = _axis_grid(room.largo, grid_size)
    y_vals = _axis_grid(room.ancho, grid_size)

    signed_pressure = []
    for y in y_vals:
        row = []
        for x in x_vals:
            row.append(
                _mode_pressure_value(
                    nx,
                    ny,
                    nz,
                    x,
                    y,
                    ear_height,
                    room.largo,
                    room.ancho,
                    room.alto,
                )
            )
        signed_pressure.append(row)
    magnitude = [[abs(value) for value in row] for row in signed_pressure]

    return {
        "grid_x": x_vals,
        "grid_y": y_vals,
        "pressure": signed_pressure,
        "signed_pressure": signed_pressure,
        "magnitude": magnitude,
        "quantity": "signed_normalized_pressure",
        "ear_height": ear_height,
    }


def _select_modes(
    room: Room,
    modos: Optional[list[Mode]],
    max_freq: float,
    *,
    c: float | None,
    environment: Environment | None,
) -> list[Mode]:
    if modos is None:
        return calculate_modes(room, f_max=max_freq, c=c, environment=environment)
    return [mode for mode in modos if mode.frecuencia <= max_freq]


def compute_pressure_map(
    room: Room,
    modos: Optional[list[Mode]] = None,
    max_freq: float = 300.0,
    ear_height: float = 1.2,
    grid_size: int = 100,
    *,
    c: float | None = None,
    environment: Environment | None = None,
) -> dict:
    max_freq = _finite(max_freq, "max_freq")
    if max_freq <= 0.0:
        raise ValueError("max_freq must be positive")
    _validate_grid_size(grid_size)
    ear_height = _validate_coordinate(ear_height, room.alto, "ear_height")
    filtered_modes = _select_modes(
        room,
        modos,
        max_freq,
        c=c,
        environment=environment,
    )

    x_vals = _axis_grid(room.largo, grid_size)
    y_vals = _axis_grid(room.ancho, grid_size)
    energy_grid = [[0.0] * grid_size for _ in range(grid_size)]

    for mode in filtered_modes:
        nx, ny, nz = mode.indices
        energy_weight = mode.energy_weight
        for y_index, y in enumerate(y_vals):
            for x_index, x in enumerate(x_vals):
                pressure = _mode_pressure_value(
                    nx,
                    ny,
                    nz,
                    x,
                    y,
                    ear_height,
                    room.largo,
                    room.ancho,
                    room.alto,
                )
                energy_grid[y_index][x_index] += energy_weight * pressure * pressure

    max_energy = max((max(row) for row in energy_grid), default=0.0)
    if max_energy > 0.0:
        normalized_energy = [
            [value / max_energy for value in row] for row in energy_grid
        ]
        magnitude = [
            [math.sqrt(value / max_energy) for value in row] for row in energy_grid
        ]
    else:
        normalized_energy = [[0.0] * grid_size for _ in range(grid_size)]
        magnitude = [[0.0] * grid_size for _ in range(grid_size)]

    result = {
        "grid_x": x_vals,
        "grid_y": y_vals,
        # Combined modes have no defined relative phase, so the legacy key is
        # explicitly an RMS magnitude rather than a signed pressure.
        "pressure": magnitude,
        "magnitude": magnitude,
        "energy": normalized_energy,
        "signed_pressure": None,
        "quantity": "normalized_weighted_rms_magnitude",
        "max_freq": max_freq,
        "ear_height": ear_height,
        "num_modos": len(filtered_modes),
    }
    if not filtered_modes:
        result["warnings"] = [f"No room modes exist at or below {max_freq:g} Hz."]
    return result


def spectral_levels_db_at(
    room: Room,
    modos: list[Mode],
    x: float,
    y: float,
    z: float,
    *,
    db_floor: float = -80.0,
) -> list[float]:
    """Return weighted modal magnitudes as spectral levels in dB."""

    x = _validate_coordinate(x, room.largo, "x")
    y = _validate_coordinate(y, room.ancho, "y")
    z = _validate_coordinate(z, room.alto, "z")
    db_floor = _finite(db_floor, "db_floor")
    if db_floor >= 0.0:
        raise ValueError("db_floor must be negative")
    amplitude_floor = 10.0 ** (db_floor / 20.0)

    levels = []
    for mode in modos:
        nx, ny, nz = mode.indices
        signed = _mode_pressure_value(
            nx,
            ny,
            nz,
            x,
            y,
            z,
            room.largo,
            room.ancho,
            room.alto,
        )
        weighted_magnitude = math.sqrt(mode.energy_weight) * abs(signed)
        levels.append(20.0 * math.log10(max(weighted_magnitude, amplitude_floor)))
    return levels


def _spectral_flatness_score(levels_db: list[float]) -> float:
    if not levels_db:
        return 0.0
    mean = sum(levels_db) / len(levels_db)
    return math.sqrt(
        sum((level - mean) ** 2 for level in levels_db) / len(levels_db)
    )


def find_optimal_listening(
    room: Room,
    modos: Optional[list[Mode]] = None,
    max_freq: float = 300.0,
    ear_height: float = 1.2,
    grid_size: int = 50,
    *,
    boundary_margin: float | None = None,
    current_position: tuple[float, float] | None = None,
    db_floor: float = -80.0,
    c: float | None = None,
    environment: Environment | None = None,
) -> dict:
    """Minimize standard deviation of weighted modal levels in spectral dB."""

    max_freq = _finite(max_freq, "max_freq")
    if max_freq <= 0.0:
        raise ValueError("max_freq must be positive")
    _validate_grid_size(grid_size)
    ear_height = _validate_coordinate(ear_height, room.alto, "ear_height")
    db_floor = _finite(db_floor, "db_floor")
    if db_floor >= 0.0:
        raise ValueError("db_floor must be negative")

    if boundary_margin is None:
        boundary_margin = min(0.5, 0.1 * min(room.largo, room.ancho))
    boundary_margin = _finite(boundary_margin, "boundary_margin")
    if boundary_margin < 0.0:
        raise ValueError("boundary_margin must be non-negative")
    if 2.0 * boundary_margin >= min(room.largo, room.ancho):
        raise ValueError("boundary_margin leaves no physical listening area")

    filtered_modes = _select_modes(
        room,
        modos,
        max_freq,
        c=c,
        environment=environment,
    )
    x_vals = _axis_grid(room.largo, grid_size, boundary_margin)
    y_vals = _axis_grid(room.ancho, grid_size, boundary_margin)

    if current_position is None:
        reference_x = min(
            room.largo - boundary_margin,
            max(boundary_margin, 0.38 * room.largo),
        )
        reference_y = min(
            room.ancho - boundary_margin,
            max(boundary_margin, 0.5 * room.ancho),
        )
    else:
        if len(current_position) != 2:
            raise ValueError("current_position must contain x and y")
        reference_x = _validate_coordinate(current_position[0], room.largo, "current_position.x")
        reference_y = _validate_coordinate(current_position[1], room.ancho, "current_position.y")
        if not (
            boundary_margin <= reference_x <= room.largo - boundary_margin
            and boundary_margin <= reference_y <= room.ancho - boundary_margin
        ):
            raise ValueError("current_position must respect boundary_margin")

    if not filtered_modes:
        return {
            "x": reference_x,
            "y": reference_y,
            "score": 0.0,
            "score_unit": "dB standard deviation",
            "boundary_margin": boundary_margin,
            "reference_position": {"x": reference_x, "y": reference_y},
            "reference_score_db": 0.0,
            "movement_m": 0.0,
            "movement": {"dx_m": 0.0, "dy_m": 0.0, "distance_m": 0.0},
            "improvement_db": 0.0,
            "db_improvement": 0.0,
            "warnings": [f"No room modes exist at or below {max_freq:g} Hz."],
        }

    best_score = math.inf
    best_x = reference_x
    best_y = reference_y
    for y in y_vals:
        for x in x_vals:
            score = _spectral_flatness_score(
                spectral_levels_db_at(
                    room,
                    filtered_modes,
                    x,
                    y,
                    ear_height,
                    db_floor=db_floor,
                )
            )
            if score < best_score:
                best_score = score
                best_x = x
                best_y = y

    reference_score = _spectral_flatness_score(
        spectral_levels_db_at(
            room,
            filtered_modes,
            reference_x,
            reference_y,
            ear_height,
            db_floor=db_floor,
        )
    )
    dx = best_x - reference_x
    dy = best_y - reference_y
    movement = math.hypot(dx, dy)
    improvement = max(0.0, reference_score - best_score)
    return {
        "x": best_x,
        "y": best_y,
        "score": best_score,
        "score_unit": "dB standard deviation",
        "boundary_margin": boundary_margin,
        "reference_position": {"x": reference_x, "y": reference_y},
        "reference_score_db": reference_score,
        "movement_m": movement,
        "movement": {"dx_m": dx, "dy_m": dy, "distance_m": movement},
        "improvement_db": improvement,
        "db_improvement": improvement,
    }

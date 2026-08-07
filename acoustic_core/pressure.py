import math
from typing import Optional
from .models import Room, Mode, BANDAS_OCTAVA
from .resonance import calculate_modes


def _mode_pressure_at(
    nx: int, ny: int, nz: int,
    x: float, y: float, z: float,
    largo: float, ancho: float, alto: float,
) -> float:
    return (
        math.cos(nx * math.pi * x / largo) *
        math.cos(ny * math.pi * y / ancho) *
        math.cos(nz * math.pi * z / alto)
    )


def compute_single_mode_grid(
    room: Room,
    nx: int, ny: int, nz: int,
    ear_height: float = 1.2,
    grid_size: int = 100,
) -> dict:
    x_vals = [i * room.largo / (grid_size - 1) for i in range(grid_size)]
    y_vals = [i * room.ancho / (grid_size - 1) for i in range(grid_size)]

    pressure = []
    for y in y_vals:
        row = []
        for x in x_vals:
            p = _mode_pressure_at(nx, ny, nz, x, y, ear_height, room.largo, room.ancho, room.alto)
            row.append(round(p, 6))
        pressure.append(row)

    return {
        "grid_x": [round(v, 3) for v in x_vals],
        "grid_y": [round(v, 3) for v in y_vals],
        "pressure": pressure,
        "ear_height": ear_height,
    }


def compute_pressure_map(
    room: Room,
    modos: Optional[list[Mode]] = None,
    max_freq: float = 300.0,
    ear_height: float = 1.2,
    grid_size: int = 100,
) -> dict:
    if modos is None:
        modos = calculate_modes(room)

    modos_filtrados = [m for m in modos if m.frecuencia <= max_freq]
    if not modos_filtrados:
        modos_filtrados = modos[:1]

    x_vals = [i * room.largo / (grid_size - 1) for i in range(grid_size)]
    y_vals = [i * room.ancho / (grid_size - 1) for i in range(grid_size)]

    max_energy = 0.0
    energy_grid = [[0.0] * grid_size for _ in range(grid_size)]

    for modo in modos_filtrados:
        nx, ny, nz = modo.indices
        for yi, y in enumerate(y_vals):
            for xi, x in enumerate(x_vals):
                p = _mode_pressure_at(nx, ny, nz, x, y, ear_height, room.largo, room.ancho, room.alto)
                energy_grid[yi][xi] += p * p

    for row in energy_grid:
        max_energy = max(max_energy, max(row))

    if max_energy > 0:
        pressure = [[round(v / max_energy, 6) for v in row] for row in energy_grid]
    else:
        pressure = [[0.0] * grid_size for _ in range(grid_size)]

    return {
        "grid_x": [round(v, 3) for v in x_vals],
        "grid_y": [round(v, 3) for v in y_vals],
        "pressure": pressure,
        "max_freq": max_freq,
        "ear_height": ear_height,
        "num_modos": len(modos_filtrados),
    }


def find_optimal_listening(
    room: Room,
    modos: Optional[list[Mode]] = None,
    max_freq: float = 300.0,
    ear_height: float = 1.2,
    grid_size: int = 50,
) -> dict:
    if modos is None:
        modos = calculate_modes(room)

    modos_filtrados = [m for m in modos if m.frecuencia <= max_freq]
    if not modos_filtrados:
        modos_filtrados = modos[:1]

    x_vals = [i * room.largo / (grid_size - 1) for i in range(grid_size)]
    y_vals = [i * room.ancho / (grid_size - 1) for i in range(grid_size)]

    best_score = float('inf')
    best_x = best_y = 0.0

    for y in y_vals:
        for x in x_vals:
            pressures = []
            for modo in modos_filtrados:
                nx, ny, nz = modo.indices
                p = _mode_pressure_at(nx, ny, nz, x, y, ear_height, room.largo, room.ancho, room.alto)
                pressures.append(abs(p))

            mean = sum(pressures) / len(pressures)
            variance = sum((v - mean) ** 2 for v in pressures) / len(pressures)

            if variance < best_score:
                best_score = variance
                best_x = x
                best_y = y

    return {
        "x": round(best_x, 3),
        "y": round(best_y, 3),
        "score": round(best_score, 6),
    }

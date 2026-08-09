"""Legacy JSON adapter for the optional sparse P1 FEM server solver."""

from __future__ import annotations

import math


C = 343.0


def _numerical_api():
    try:
        from acoustic_numerics.fem2d import masked_rectangle_mesh, rectangle_mesh, solve_fem_modes
    except ImportError as exc:
        raise RuntimeError("2D modal FEM is server-only and requires NumPy and SciPy") from exc
    return rectangle_mesh, masked_rectangle_mesh, solve_fem_modes


def compute_2d_modes(
    width: float,
    height: float,
    grid_nx: int = 20,
    grid_ny: int = 20,
    num_modes: int = 5,
    exclude_regions: list[dict] | None = None,
) -> list[dict]:
    """Preserve the historical rectangular API using an actual sparse FEM solve."""

    if width <= 0.0 or height <= 0.0:
        raise ValueError("width and height must be positive")
    if grid_nx < 2 or grid_ny < 2:
        raise ValueError("grid dimensions must be at least 2")
    rectangle_mesh, masked_rectangle_mesh, solve_fem_modes = _numerical_api()
    if exclude_regions:
        mesh = masked_rectangle_mesh(width, height, grid_nx, grid_ny, exclude_regions)
    else:
        mesh = rectangle_mesh(width, height, grid_nx, grid_ny)
    result = solve_fem_modes(mesh, num_modes=num_modes, sound_speed_m_s=C)

    grid_x = [i * width / (grid_nx - 1) for i in range(grid_nx)]
    grid_y = [j * height / (grid_ny - 1) for j in range(grid_ny)]
    output: list[dict] = []
    for mode in result.modes:
        real_shape = [float(value.real) for value in mode.shape]
        scale = max((abs(value) for value in real_shape), default=1.0) or 1.0
        shape_2d = [[0.0 for _ in range(grid_nx)] for _ in range(grid_ny)]
        for node, value in zip(mesh.nodes, real_shape, strict=True):
            i = int(round(float(node[0]) / width * (grid_nx - 1)))
            j = int(round(float(node[1]) / height * (grid_ny - 1)))
            if 0 <= i < grid_nx and 0 <= j < grid_ny:
                shape_2d[j][i] = value / scale
        output.append(
            {
                "mode": mode.mode_index,
                "frequency_hz": mode.frequency_hz,
                "frequency_imag_hz": mode.complex_frequency_hz.imag,
                "decay_rate_neper_s": mode.decay_rate_neper_s,
                "rt60_estimate_s": mode.rt60_s if math.isfinite(mode.rt60_s) else 0.0,
                "eigenvalue_per_m2": mode.eigenvalue_per_m2.real,
                "residual": mode.residual,
                "shape_2d": shape_2d,
                "grid_x": grid_x,
                "grid_y": grid_y,
                "mesh_nodes": len(mesh.nodes),
                "mesh_triangles": len(mesh.elements),
                "method": result.method,
                "research_status": result.research_status,
            }
        )
    return output

"""Compatibility adapters for the optional server numerical package.

This module intentionally imports NumPy/SciPy-backed code only when a numerical
function is called.  Importing ``acoustic_core`` therefore remains possible in a
FREE/core-only installation.
"""

from __future__ import annotations

import cmath
import math
from typing import Callable


C = 343.0
RHO = 1.2


def _numerical_api():
    try:
        from acoustic_numerics.finite_impedance import rt60_from_decay_rate, solve_axial_modes
    except ImportError as exc:
        raise RuntimeError(
            "finite-impedance modes are server-only and require NumPy and SciPy"
        ) from exc
    return solve_axial_modes, rt60_from_decay_rate


def axial_modes_finite_impedance(
    L_m: float,
    Z_wall_real: float | complex | Callable[[complex], complex] = 10000,
    Z_wall_imag: float = 0,
    max_modes: int = 5,
) -> list[dict]:
    """Return legacy dictionaries for a rigid/impedance 1D fluid column.

    ``damping_neper_s`` is now the positive amplitude decay rate in Np/s.
    ``frequency_imag_hz`` retains the signed complex-frequency component for
    callers that need the ``exp(-i omega t)`` convention explicitly.
    """

    solve_axial_modes, _ = _numerical_api()
    if callable(Z_wall_real):
        impedance = (
            Z_wall_real
            if Z_wall_imag == 0.0
            else lambda frequency_hz: complex(Z_wall_real(frequency_hz)) + 1j * Z_wall_imag
        )
    else:
        impedance = complex(Z_wall_real) + 1j * Z_wall_imag
    numerical_modes = solve_axial_modes(
        L_m,
        impedance,
        num_modes=max_modes,
        density_kg_m3=RHO,
        sound_speed_m_s=C,
    )
    return [
        {
            "n": mode.mode_index,
            "frequency_hz": mode.frequency_real_hz,
            "frequency_imag_hz": mode.frequency_imag_hz,
            "rigid_frequency_hz": mode.rigid_frequency_hz,
            "damping_neper_s": mode.decay_rate_neper_s,
            "decay_rate_neper_s": mode.decay_rate_neper_s,
            "rt60_estimate_s": mode.rt60_s if math.isfinite(mode.rt60_s) else 0.0,
            "shift_hz": mode.frequency_real_hz - mode.rigid_frequency_hz,
            "residual": mode.residual,
            "converged": mode.converged,
            "boundary_configuration": "rigid at x=0; locally reacting impedance at x=L",
        }
        for mode in numerical_modes
    ]


def room_modes_finite_impedance(
    L: float,
    W: float,
    H: float,
    Z_wall: float | complex | Callable[[complex], complex] = 10000,
    max_order: int = 3,
) -> list[dict]:
    """Return a separable active-axis estimate for a rectangular room.

    Each non-zero modal index uses the validated 1D rigid/impedance root on that
    axis; zero-index axes remain invariant.  This preserves the historical room
    API while clearly avoiding a claim that it solves the full six-wall nonlinear
    impedance eigenproblem.
    """

    if min(L, W, H) <= 0.0:
        raise ValueError("room dimensions must be positive")
    if max_order < 1:
        raise ValueError("max_order must be at least 1")
    solve_axial_modes, rt60_from_decay_rate = _numerical_api()
    axial_roots = {
        axis: solve_axial_modes(
            dimension,
            Z_wall,
            num_modes=max_order,
            density_kg_m3=RHO,
            sound_speed_m_s=C,
        )
        for axis, dimension in enumerate((L, W, H))
    }

    modes: list[dict] = []
    for nx in range(max_order + 1):
        for ny in range(max_order + 1):
            for nz in range(max_order + 1):
                indices = (nx, ny, nz)
                if indices == (0, 0, 0):
                    continue
                component_wavenumbers = [
                    0.0j if order == 0 else axial_roots[axis][order - 1].wavenumber_per_m
                    for axis, order in enumerate(indices)
                ]
                wavenumber = cmath.sqrt(sum(component * component for component in component_wavenumbers))
                if wavenumber.real < 0.0 or (wavenumber.real == 0.0 and wavenumber.imag > 0.0):
                    wavenumber = -wavenumber
                frequency = C * wavenumber / (2.0 * math.pi)
                rigid_wavenumber_squared = sum(
                    (order * math.pi / dimension) ** 2
                    for order, dimension in zip(indices, (L, W, H), strict=True)
                )
                rigid_frequency = C * math.sqrt(rigid_wavenumber_squared) / (2.0 * math.pi)
                decay_rate = max(0.0, -C * wavenumber.imag)
                rt60 = rt60_from_decay_rate(decay_rate)
                active_residuals = [
                    axial_roots[axis][order - 1].residual
                    for axis, order in enumerate(indices)
                    if order > 0
                ]
                modes.append(
                    {
                        "indices": list(indices),
                        "frequency_hz": float(frequency.real),
                        "frequency_imag_hz": float(frequency.imag),
                        "rigid_frequency_hz": rigid_frequency,
                        "damping": decay_rate,
                        "damping_neper_s": decay_rate,
                        "rt60_estimate_s": rt60 if math.isfinite(rt60) else 0.0,
                        "residual": max(active_residuals, default=0.0),
                        "model": "separable active-axis impedance approximation",
                    }
                )
    return sorted(modes, key=lambda mode: mode["frequency_hz"])

"""Complex axial modes for a one-dimensional impedance termination.

The model is deliberately narrow: a uniform fluid column occupies ``0 <= x <= L``.
The boundary at ``x=0`` is rigid and the boundary at ``x=L`` has the locally
reacting specific acoustic impedance ``Z`` (Pa s/m).  With the time convention
``p(x, t) = Re(P(x) exp(-i omega t))``, the dimensionless characteristic equation
is

    tan(k L) + i rho c / Z(omega / (2 pi)) = 0.

Consequently passive damping appears as ``Im(omega) < 0``.  This module reports
the positive amplitude decay rate ``-Im(omega)`` in nepers per second.  The model
does not include oblique incidence, wall structural modes, or edge losses and is
therefore a research/validation model rather than a room-acoustics standard.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, TypeAlias

import numpy as np
from scipy.optimize import root


FrequencyImpedance: TypeAlias = complex | float | Callable[[complex], complex]


@dataclass(frozen=True)
class AxialMode:
    """One complex resonance of the rigid/impedance fluid column."""

    mode_index: int
    wavenumber_per_m: complex
    frequency_hz: complex
    rigid_frequency_hz: float
    decay_rate_neper_s: float
    rt60_s: float
    residual: float
    converged: bool
    solver_evaluations: int

    @property
    def frequency_real_hz(self) -> float:
        return float(self.frequency_hz.real)

    @property
    def frequency_imag_hz(self) -> float:
        return float(self.frequency_hz.imag)

    @property
    def quality_factor(self) -> float:
        """Return ``Re(omega)/(2 gamma)`` for a decaying mode."""

        if self.decay_rate_neper_s <= 0.0:
            return math.inf
        omega_real = 2.0 * math.pi * self.frequency_hz.real
        return float(omega_real / (2.0 * self.decay_rate_neper_s))


class RootConvergenceError(RuntimeError):
    """Raised when a requested impedance resonance cannot be isolated."""


def rt60_from_decay_rate(decay_rate_neper_s: float) -> float:
    """Convert modal amplitude decay ``gamma`` [Np/s] to a 60 dB decay time.

    For ``p(t) = p0 exp(-gamma t)``, both ``20 log10(|p/p0|)`` and the
    corresponding energy level reach -60 dB at ``3 ln(10) / gamma``.
    """

    if decay_rate_neper_s < 0.0:
        raise ValueError("decay_rate_neper_s must be non-negative")
    if decay_rate_neper_s == 0.0:
        return math.inf
    return 3.0 * math.log(10.0) / decay_rate_neper_s


def _impedance_at(impedance: FrequencyImpedance, frequency_hz: complex) -> complex:
    value = impedance(frequency_hz) if callable(impedance) else impedance
    try:
        result = complex(value)
    except (TypeError, ValueError) as exc:
        raise TypeError("impedance must evaluate to a scalar complex value") from exc
    if math.isnan(result.real) or math.isnan(result.imag):
        raise ValueError("impedance returned NaN")
    if result == 0.0:
        raise ValueError("specific acoustic impedance must be non-zero")
    return result


def axial_characteristic(
    wavenumber_per_m: complex,
    length_m: float,
    impedance: FrequencyImpedance,
    *,
    density_kg_m3: float = 1.2,
    sound_speed_m_s: float = 343.0,
) -> complex:
    """Evaluate the dimensionless rigid/impedance characteristic equation.

    Frequency-dependent impedance callables receive complex frequency in hertz.
    Supporting complex arguments avoids silently discarding damping during the
    nonlinear solve.
    """

    if length_m <= 0.0:
        raise ValueError("length_m must be positive")
    if density_kg_m3 <= 0.0 or sound_speed_m_s <= 0.0:
        raise ValueError("density and sound speed must be positive")

    k = complex(wavenumber_per_m)
    frequency_hz = sound_speed_m_s * k / (2.0 * math.pi)
    z_wall = _impedance_at(impedance, frequency_hz)
    impedance_term = 0.0j if math.isinf(abs(z_wall)) else 1j * density_kg_m3 * sound_speed_m_s / z_wall
    return complex(np.tan(k * length_m) + impedance_term)


def solve_axial_mode(
    length_m: float,
    impedance: FrequencyImpedance,
    mode_index: int,
    *,
    density_kg_m3: float = 1.2,
    sound_speed_m_s: float = 343.0,
    tolerance: float = 1e-10,
    max_evaluations: int = 300,
    raise_on_failure: bool = True,
) -> AxialMode:
    """Solve one complex resonance near the corresponding rigid mode.

    The nonlinear equation is solved in the dimensionless variable ``z=kL``
    using several physically motivated starts.  The returned ``residual`` is the
    absolute value of the dimensionless characteristic equation.
    """

    if length_m <= 0.0:
        raise ValueError("length_m must be positive")
    if mode_index < 1:
        raise ValueError("mode_index must be at least 1")
    if density_kg_m3 <= 0.0 or sound_speed_m_s <= 0.0:
        raise ValueError("density and sound speed must be positive")
    if tolerance <= 0.0:
        raise ValueError("tolerance must be positive")

    rigid_z = mode_index * math.pi
    rigid_frequency = mode_index * sound_speed_m_s / (2.0 * length_m)
    z_at_rigid = _impedance_at(impedance, complex(rigid_frequency))

    characteristic_impedance = density_kg_m3 * sound_speed_m_s
    if not callable(impedance) and abs(z_at_rigid - characteristic_impedance) <= tolerance * characteristic_impedance:
        raise RootConvergenceError(
            "a purely resistive Z=rho*c termination is perfectly matched and has no finite discrete axial pole"
        )

    if math.isinf(abs(z_at_rigid)) and not callable(impedance):
        return AxialMode(
            mode_index=mode_index,
            wavenumber_per_m=complex(rigid_z / length_m),
            frequency_hz=complex(rigid_frequency),
            rigid_frequency_hz=rigid_frequency,
            decay_rate_neper_s=0.0,
            rt60_s=math.inf,
            residual=0.0,
            converged=True,
            solver_evaluations=0,
        )

    starts: list[complex] = []
    target_z = complex(rigid_z)
    if not math.isinf(abs(z_at_rigid)):
        normalized_admittance = density_kg_m3 * sound_speed_m_s / z_at_rigid
        with np.errstate(all="ignore"):
            correction = complex(np.arctan(-1j * normalized_admittance))
        if np.isfinite(correction.real) and np.isfinite(correction.imag):
            # Use the half-open principal interval [-pi/2, pi/2).  At low
            # impedance the real correction is exactly pi/2; selecting -pi/2
            # keeps mode n on the nth positive pressure-release branch.
            correction -= math.floor((correction.real + 0.5 * math.pi) / math.pi) * math.pi
            target_z = rigid_z + correction
            starts.append(target_z)

    damping_scale = 0.05
    if not math.isinf(abs(z_at_rigid)):
        damping_scale = min(2.0, max(1e-5, abs(density_kg_m3 * sound_speed_m_s / z_at_rigid)))
    starts.extend(
        [
            complex(rigid_z, -damping_scale),
            complex(rigid_z, -0.01),
            complex(rigid_z),
            complex((mode_index - 0.5) * math.pi, -0.25),
            complex((mode_index + 0.5) * math.pi, -0.25),
        ]
    )

    def packed_residual(vector: np.ndarray) -> np.ndarray:
        z_value = complex(float(vector[0]), float(vector[1]))
        try:
            value = axial_characteristic(
                z_value / length_m,
                length_m,
                impedance,
                density_kg_m3=density_kg_m3,
                sound_speed_m_s=sound_speed_m_s,
            )
        except (ValueError, TypeError, OverflowError, ZeroDivisionError):
            return np.array([1e30, 1e30], dtype=float)
        if not np.isfinite(value.real) or not np.isfinite(value.imag):
            return np.array([1e30, 1e30], dtype=float)
        return np.array([value.real, value.imag], dtype=float)

    candidates: list[tuple[float, float, complex, bool, int]] = []
    seen_starts: set[tuple[float, float]] = set()
    for start in starts:
        key = (round(start.real, 12), round(start.imag, 12))
        if key in seen_starts:
            continue
        seen_starts.add(key)
        solution = root(
            packed_residual,
            np.array([start.real, start.imag], dtype=float),
            method="hybr",
            tol=tolerance,
            options={"maxfev": max_evaluations},
        )
        solved_z = complex(float(solution.x[0]), float(solution.x[1]))
        residual = float(np.linalg.norm(packed_residual(solution.x)))
        if not np.isfinite(residual) or solved_z.real <= 0.0:
            continue
        branch_distance = abs(solved_z - target_z)
        candidates.append((residual, branch_distance, solved_z, bool(solution.success), int(solution.nfev)))

    if candidates:
        acceptable = [item for item in candidates if item[0] <= max(1e-8, 100.0 * tolerance)]
        pool = acceptable or candidates
        residual, _, solved_z, solver_success, evaluations = min(pool, key=lambda item: (item[1], item[0]))
    else:
        residual = math.inf
        solved_z = complex(rigid_z)
        solver_success = False
        evaluations = 0

    converged = bool(solver_success or residual <= max(1e-8, 100.0 * tolerance))
    if not converged and raise_on_failure:
        raise RootConvergenceError(
            f"could not isolate axial mode {mode_index}; dimensionless residual={residual:.3g}"
        )

    wavenumber = solved_z / length_m
    frequency = sound_speed_m_s * wavenumber / (2.0 * math.pi)
    omega = sound_speed_m_s * wavenumber
    decay_rate = max(0.0, float(-omega.imag))
    if decay_rate < tolerance * sound_speed_m_s / length_m:
        decay_rate = 0.0

    return AxialMode(
        mode_index=mode_index,
        wavenumber_per_m=complex(wavenumber),
        frequency_hz=complex(frequency),
        rigid_frequency_hz=rigid_frequency,
        decay_rate_neper_s=decay_rate,
        rt60_s=rt60_from_decay_rate(decay_rate),
        residual=residual,
        converged=converged,
        solver_evaluations=evaluations,
    )


def solve_axial_modes(
    length_m: float,
    impedance: FrequencyImpedance,
    num_modes: int = 5,
    **solver_options: float | int | bool,
) -> list[AxialMode]:
    """Solve the first ``num_modes`` non-zero axial resonances."""

    if num_modes < 1:
        raise ValueError("num_modes must be at least 1")
    return [
        solve_axial_mode(length_m, impedance, mode_index, **solver_options)
        for mode_index in range(1, num_modes + 1)
    ]


__all__ = [
    "AxialMode",
    "FrequencyImpedance",
    "RootConvergenceError",
    "axial_characteristic",
    "rt60_from_decay_rate",
    "solve_axial_mode",
    "solve_axial_modes",
]

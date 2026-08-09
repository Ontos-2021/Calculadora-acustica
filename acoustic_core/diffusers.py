"""Quadratic-residue diffuser geometry and diffusion screening metrics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import cmath
import math

from .models import BANDAS_OCTAVA


C = 343.0
DIFFUSER_ESTIMATE_LABEL = "engineering_estimate_not_iso_test_or_certification"
QRD_REFERENCE = (
    "M. R. Schroeder, Diffuse Sound Reflection by Maximum-Length Sequences, "
    "JASA 57 (1975); public quadratic-residue construction."
)
ISO17497_STYLE_NOTE = (
    "Public ISO 17497-2-style normalized polar-energy equation; valid standard "
    "results additionally require the prescribed measurement geometry and reference surface. "
    "This calculation is not an ISO test or certification."
)


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _positive(value: float, name: str) -> float:
    converted = _finite(value, name)
    if converted <= 0.0:
        raise ValueError(f"{name} must be positive")
    return converted


def _primes_up_to(n: int) -> list[int]:
    if n < 2:
        return []
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for candidate in range(2, math.isqrt(n) + 1):
        if sieve[candidate]:
            for multiple in range(candidate * candidate, n + 1, candidate):
                sieve[multiple] = False
    return [candidate for candidate, prime in enumerate(sieve) if prime]


PRIMES = _primes_up_to(200)


def _is_prime(candidate: int) -> bool:
    if candidate < 2:
        return False
    if candidate == 2:
        return True
    if candidate % 2 == 0:
        return False
    return all(candidate % divisor for divisor in range(3, math.isqrt(candidate) + 1, 2))


def _nearest_prime(n: int) -> int:
    """Return the mathematically nearest prime, preferring the lower on a tie."""

    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an integer")
    if n <= 2:
        return 2
    distance = 0
    while True:
        lower = n - distance
        upper = n + distance
        if lower >= 2 and _is_prime(lower):
            return lower
        if upper != lower and _is_prime(upper):
            return upper
        distance += 1


nearest_prime = _nearest_prime


def _manufacturability(
    cell_width_m: float,
    actual_max_depth_m: float,
    lower_frequency_hz: float,
    upper_frequency_hz: float,
    *,
    minimum_cell_width_m: float,
    maximum_depth_to_width_ratio: float,
) -> dict:
    warnings: list[str] = []
    aspect_ratio = actual_max_depth_m / cell_width_m
    if cell_width_m < minimum_cell_width_m:
        warnings.append(
            f"Cell width is below the {minimum_cell_width_m:g} m screening fabrication limit."
        )
    if aspect_ratio > maximum_depth_to_width_ratio:
        warnings.append(
            "Maximum depth-to-width ratio exceeds the screening fabrication limit."
        )
    if upper_frequency_hz <= lower_frequency_hz:
        warnings.append(
            "Cell width places the spatial-aliasing upper estimate at or below the design frequency."
        )
    return {
        "manufacturable": not warnings,
        "minimum_cell_width_m": minimum_cell_width_m,
        "maximum_depth_to_width_ratio": maximum_depth_to_width_ratio,
        "actual_depth_to_width_ratio": round(aspect_ratio, 3),
        "maximum_width_for_design_frequency_m": round(C / (2.0 * lower_frequency_hz), 4),
        "warnings": warnings,
        "limits_are": "screening fabrication heuristics, not normative requirements",
    }


def qrd_well_depths(
    design_freq_hz: float,
    prime_n: int = 17,
    well_width_m: float = 0.05,
    *,
    minimum_well_width_m: float = 0.01,
    maximum_depth_to_width_ratio: float = 12.0,
    sound_speed_m_s: float = C,
) -> dict:
    """Construct a one-dimensional quadratic-residue diffuser sequence."""

    try:
        frequency = _positive(design_freq_hz, "design_freq_hz")
        width = _positive(well_width_m, "well_width_m")
        sound_speed = _positive(sound_speed_m_s, "sound_speed_m_s")
        minimum_width = _positive(minimum_well_width_m, "minimum_well_width_m")
        maximum_aspect = _positive(
            maximum_depth_to_width_ratio, "maximum_depth_to_width_ratio"
        )
        if isinstance(prime_n, bool) or not isinstance(prime_n, int) or prime_n < 3:
            raise ValueError("prime_n must be an integer of at least 3")
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}

    requested_n = prime_n
    prime = _nearest_prime(prime_n)
    wavelength = sound_speed / frequency
    design_max_depth = wavelength / 2.0
    sequence = [(index * index) % prime for index in range(prime)]
    depths = [design_max_depth * residue / prime for residue in sequence]
    actual_max_depth = max(depths)
    lower_frequency = sound_speed / (2.0 * design_max_depth)
    upper_frequency = sound_speed / (2.0 * width)
    manufacturing = _manufacturability(
        width,
        actual_max_depth,
        lower_frequency,
        upper_frequency,
        minimum_cell_width_m=minimum_width,
        maximum_depth_to_width_ratio=maximum_aspect,
    )
    return {
        "type": "QRD",
        "requested_prime_n": requested_n,
        "prime_n": prime,
        "design_freq_hz": frequency,
        "well_width_m": width,
        "total_width_m": round(prime * width, 3),
        "max_depth_m": round(design_max_depth, 4),
        "actual_max_well_depth_m": round(actual_max_depth, 4),
        "lower_useful_frequency_hz": round(lower_frequency, 1),
        "upper_useful_frequency_hz": round(upper_frequency, 1),
        "min_effective_freq_hz": round(lower_frequency, 1),
        "useful_frequency_range_valid": upper_frequency > lower_frequency,
        "well_depths_m": [round(depth, 4) for depth in depths],
        "sequence": sequence,
        "construction": "s[n] = n^2 mod N; depth[n] = s[n] * c / (2*N*f_design)",
        "manufacturability": manufacturing,
        "reference": QRD_REFERENCE,
        "estimate_label": DIFFUSER_ESTIMATE_LABEL,
    }


def skyline_well_depths(
    design_freq_hz: float,
    grid_n: int = 7,
    well_size_m: float = 0.05,
    *,
    minimum_well_size_m: float = 0.01,
    maximum_depth_to_width_ratio: float = 12.0,
    sound_speed_m_s: float = C,
) -> dict:
    """Construct a 2D quadratic-residue Skyline sequence.

    The residue at row ``i``, column ``j`` is ``(i^2 + j^2) mod N`` for prime
    ``N``.  This separable two-dimensional construction replaces the former
    arbitrary row/column multiplication.
    """

    try:
        frequency = _positive(design_freq_hz, "design_freq_hz")
        cell_size = _positive(well_size_m, "well_size_m")
        sound_speed = _positive(sound_speed_m_s, "sound_speed_m_s")
        minimum_size = _positive(minimum_well_size_m, "minimum_well_size_m")
        maximum_aspect = _positive(
            maximum_depth_to_width_ratio, "maximum_depth_to_width_ratio"
        )
        if isinstance(grid_n, bool) or not isinstance(grid_n, int) or grid_n < 2:
            raise ValueError("grid_n must be an integer of at least 2")
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}

    requested_n = grid_n
    prime = _nearest_prime(grid_n)
    design_max_depth = sound_speed / (2.0 * frequency)
    sequence_2d = [
        [((row * row) + (column * column)) % prime for column in range(prime)]
        for row in range(prime)
    ]
    depths_2d = [
        [design_max_depth * residue / prime for residue in row]
        for row in sequence_2d
    ]
    actual_max_depth = max(max(row) for row in depths_2d)
    lower_frequency = sound_speed / (2.0 * design_max_depth)
    upper_frequency = sound_speed / (2.0 * cell_size)
    manufacturing = _manufacturability(
        cell_size,
        actual_max_depth,
        lower_frequency,
        upper_frequency,
        minimum_cell_width_m=minimum_size,
        maximum_depth_to_width_ratio=maximum_aspect,
    )
    return {
        "type": "Skyline",
        "requested_grid_n": requested_n,
        "grid_n": prime,
        "modulus_prime": prime,
        "design_freq_hz": frequency,
        "well_size_m": cell_size,
        "total_width_m": round(prime * cell_size, 3),
        "max_depth_m": round(design_max_depth, 4),
        "actual_max_well_depth_m": round(actual_max_depth, 4),
        "lower_useful_frequency_hz": round(lower_frequency, 1),
        "upper_useful_frequency_hz": round(upper_frequency, 1),
        "min_effective_freq_hz": round(lower_frequency, 1),
        "useful_frequency_range_valid": upper_frequency > lower_frequency,
        "well_depths_m": [
            [round(depth, 4) for depth in row] for row in depths_2d
        ],
        "sequence_2d": sequence_2d,
        "construction": "s[i,j] = (i^2 + j^2) mod N; depth = s*c/(2*N*f_design)",
        "manufacturability": manufacturing,
        "reference": QRD_REFERENCE,
        "estimate_label": DIFFUSER_ESTIMATE_LABEL,
    }


def _polar_energies(
    polar_response: Mapping[float, float] | Sequence[float],
    response_unit: str,
) -> list[float]:
    if isinstance(polar_response, Mapping):
        raw_values = list(polar_response.values())
    elif isinstance(polar_response, Sequence) and not isinstance(
        polar_response, (str, bytes)
    ):
        raw_values = list(polar_response)
    else:
        raise TypeError("polar_response must be a mapping or sequence")
    if len(raw_values) < 2:
        raise ValueError("polar_response requires at least two angular samples")
    values = [_finite(value, "polar response value") for value in raw_values]
    unit = response_unit.lower().strip()
    if unit in {"db", "spl_db", "level_db"}:
        maximum = max(values)
        energies = [10.0 ** ((value - maximum) / 10.0) for value in values]
    elif unit in {"pressure", "amplitude", "linear_pressure"}:
        scale = max(abs(value) for value in values)
        if scale == 0.0:
            raise ValueError("polar_response must contain non-zero scattered energy")
        energies = [(value / scale) ** 2 for value in values]
    elif unit in {"energy", "intensity", "power"}:
        if any(value < 0.0 for value in values):
            raise ValueError("energy polar responses must be non-negative")
        scale = max(values)
        if scale == 0.0:
            raise ValueError("polar_response must contain non-zero scattered energy")
        energies = [value / scale for value in values]
    else:
        raise ValueError("response_unit must be 'pressure', 'energy', or 'db'")
    return energies


def polar_diffusion_coefficient(
    polar_response: Mapping[float, float] | Sequence[float],
    *,
    response_unit: str = "pressure",
) -> float:
    """Compute the bounded polar-energy diffusion coefficient.

    ``d = ((sum E)^2 - sum(E^2)) / ((n-1) * sum(E^2))``.  Equal energy at
    every angle gives one; all energy in one angular sample gives zero.
    """

    energies = _polar_energies(polar_response, response_unit)
    energy_sum = sum(energies)
    square_sum = sum(value * value for value in energies)
    coefficient = (
        (energy_sum * energy_sum - square_sum)
        / ((len(energies) - 1) * square_sum)
    )
    return min(1.0, max(0.0, coefficient))


def normalized_diffusion_coefficient(
    polar_response: Mapping[float, float] | Sequence[float],
    *,
    reference_response: Mapping[float, float] | Sequence[float] | None = None,
    response_unit: str = "pressure",
) -> float:
    """Return sample diffusion, optionally normalized against a flat reference."""

    sample = polar_diffusion_coefficient(
        polar_response,
        response_unit=response_unit,
    )
    if reference_response is None:
        return sample
    reference = polar_diffusion_coefficient(
        reference_response,
        response_unit=response_unit,
    )
    if reference >= 1.0 - 1e-12:
        raise ValueError("reference diffusion is one; normalized result is undefined")
    normalized = (sample - reference) / (1.0 - reference)
    return min(1.0, max(0.0, normalized))


def diffusion_coefficient_diagnostics(
    polar_response: Mapping[float, float] | Sequence[float],
    *,
    reference_response: Mapping[float, float] | Sequence[float] | None = None,
    response_unit: str = "pressure",
) -> dict:
    """JSON-friendly coefficient result with formula and qualification."""

    sample = polar_diffusion_coefficient(polar_response, response_unit=response_unit)
    reference = None
    if reference_response is not None:
        reference = polar_diffusion_coefficient(
            reference_response,
            response_unit=response_unit,
        )
    normalized = normalized_diffusion_coefficient(
        polar_response,
        reference_response=reference_response,
        response_unit=response_unit,
    )
    return {
        "sample_diffusion_coefficient": round(sample, 6),
        "reference_diffusion_coefficient": (
            None if reference is None else round(reference, 6)
        ),
        "normalized_diffusion_coefficient": round(normalized, 6),
        "response_unit": response_unit,
        "formula": "((sum(E))^2-sum(E^2))/((n-1)*sum(E^2))",
        "normalization": "(d_sample-d_reference)/(1-d_reference)",
        "implementation_note": ISO17497_STYLE_NOTE,
        "estimate_label": DIFFUSER_ESTIMATE_LABEL,
    }


def simulate_qrd_polar_response(
    well_depths_m: Sequence[float],
    frequency_hz: float,
    well_width_m: float,
    *,
    angles_deg: Sequence[float] | None = None,
    sound_speed_m_s: float = C,
) -> dict[float, float]:
    """Simulate a simple far-field QRD array factor for screening only."""

    if not isinstance(well_depths_m, Sequence) or isinstance(
        well_depths_m, (str, bytes)
    ):
        raise TypeError("well_depths_m must be a sequence")
    depths = [_finite(depth, "well depth") for depth in well_depths_m]
    if len(depths) < 2 or any(depth < 0.0 for depth in depths):
        raise ValueError("at least two non-negative well depths are required")
    frequency = _positive(frequency_hz, "frequency_hz")
    width = _positive(well_width_m, "well_width_m")
    sound_speed = _positive(sound_speed_m_s, "sound_speed_m_s")
    if angles_deg is None:
        angles = [float(angle) for angle in range(-90, 91, 5)]
    else:
        angles = [_finite(angle, "polar angle") for angle in angles_deg]
        if len(angles) < 2:
            raise ValueError("angles_deg requires at least two samples")
    if any(not -90.0 <= angle <= 90.0 for angle in angles):
        raise ValueError("polar angles must be in [-90, 90] degrees")

    wave_number = 2.0 * math.pi * frequency / sound_speed
    center = (len(depths) - 1) / 2.0
    response: dict[float, float] = {}
    for angle in angles:
        sine = math.sin(math.radians(angle))
        pressure = 0j
        for index, depth in enumerate(depths):
            position = (index - center) * width
            reflection_phase = 2.0 * wave_number * depth
            observation_phase = wave_number * position * sine
            pressure += cmath.exp(1j * (reflection_phase + observation_phase))
        response[angle] = abs(pressure) / len(depths)
    maximum = max(response.values())
    if maximum > 0.0:
        response = {angle: value / maximum for angle, value in response.items()}
    return response


def estimate_diffusion_coefficient_heuristic(
    design_freq_hz: float,
    max_depth_m: float,
    *,
    well_width_m: float | None = None,
    sound_speed_m_s: float = C,
) -> dict[str, float]:
    """Legacy-shaped octave curve, explicitly a geometry-sensitive heuristic."""

    design_frequency = _positive(design_freq_hz, "design_freq_hz")
    maximum_depth = _positive(max_depth_m, "max_depth_m")
    sound_speed = _positive(sound_speed_m_s, "sound_speed_m_s")
    width = None if well_width_m is None else _positive(well_width_m, "well_width_m")
    result: dict[str, float] = {}
    for band in BANDAS_OCTAVA:
        frequency = float(band)
        ratio = frequency / design_frequency
        if ratio < 0.25:
            envelope = 0.05
        elif ratio < 0.5:
            envelope = 0.1 + 0.3 * (ratio - 0.25) / 0.25
        elif ratio < 1.0:
            envelope = 0.4 + 0.4 * (ratio - 0.5) / 0.5
        elif ratio < 2.0:
            envelope = 0.8 + 0.15 * (ratio - 1.0)
        else:
            envelope = 0.95 - 0.1 * min(ratio - 2.0, 1.0)

        reflection_path_cycles = 2.0 * frequency * maximum_depth / sound_speed
        depth_factor = 1.0 - math.exp(-3.0 * reflection_path_cycles)
        width_factor = 1.0
        if width is not None:
            upper_frequency = sound_speed / (2.0 * width)
            if frequency > upper_frequency:
                width_factor = upper_frequency / frequency
        result[band] = round(
            min(1.0, max(0.0, envelope * depth_factor * width_factor)),
            3,
        )
    return result


def estimate_diffusion_coefficient(
    design_freq_hz: float,
    max_depth_m: float,
) -> dict[str, float]:
    """Compatibility wrapper for the explicitly named heuristic estimate."""

    return estimate_diffusion_coefficient_heuristic(
        design_freq_hz,
        max_depth_m,
    )

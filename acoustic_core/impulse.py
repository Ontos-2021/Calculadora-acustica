"""Rectangular-room image sources and ISO 3382-style model metrics.

The image-source amplitudes use a unit monopole pressure at one metre.  Wall
absorption only defines the magnitude of a pressure reflection coefficient,
``|R| = sqrt(1 - alpha)``.  In the absence of impedance/phase data this module
assumes a zero-phase (positive real) reflection.  A caller can explicitly set
individual walls to a pi phase shift with ``phase_signs``.
"""

import math
from numbers import Real
from typing import Iterable, Optional

from .models import BANDAS_OCTAVA, Room


WALL_KEYS = ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max")


def validate_position(
    room: Room,
    position: Iterable[float],
    label: str = "position",
    *,
    strictly_inside: bool = True,
) -> tuple[float, float, float]:
    """Validate and return a finite Cartesian point in a rectangular room."""
    try:
        coordinates = tuple(position)
    except TypeError as exc:
        raise ValueError(f"{label} must contain three coordinates") from exc
    if len(coordinates) != 3:
        raise ValueError(f"{label} must contain exactly three coordinates")

    dimensions = (room.largo, room.ancho, room.alto)
    result = []
    for axis, (coordinate, dimension) in enumerate(zip(coordinates, dimensions)):
        if isinstance(coordinate, bool) or not isinstance(coordinate, Real):
            raise ValueError(f"{label}[{axis}] must be a real number")
        value = float(coordinate)
        if not math.isfinite(value):
            raise ValueError(f"{label}[{axis}] must be finite")
        valid = 0.0 < value < dimension if strictly_inside else 0.0 <= value <= dimension
        if not valid:
            relation = "strictly inside" if strictly_inside else "inside"
            raise ValueError(
                f"{label}[{axis}]={value} must be {relation} [0, {dimension}]"
            )
        result.append(value)
    return result[0], result[1], result[2]


def validate_source_receiver(
    room: Room,
    source: Iterable[float],
    receiver: Iterable[float],
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Validate source/receiver positions and reject the singular zero path."""
    source_position = validate_position(room, source, "source")
    receiver_position = validate_position(room, receiver, "receiver")
    if source_position == receiver_position:
        raise ValueError("source and receiver must not be coincident")
    return source_position, receiver_position


def _image_position(s: float, L: float, k: int) -> tuple[float, int, int]:
    """Return one-dimensional image position and positive/negative wall hits.

    ``abs(k)`` is the number of reflections on this axis.  Positive odd indices
    start at the positive wall and negative odd indices at the negative wall.
    The indexing preserves the legacy ``k=1 -> 2L-s`` and ``k=-1 -> -s``
    convention while enumerating every image exactly once.
    """
    if not isinstance(k, int) or isinstance(k, bool):
        raise ValueError("image index k must be an integer")
    if not math.isfinite(L) or L <= 0:
        raise ValueError("room dimension L must be finite and positive")
    if not math.isfinite(s):
        raise ValueError("source coordinate must be finite")

    if k % 2:
        image = (k + 1) * L - s
    else:
        image = s - k * L

    if k > 0:
        positive_count = (k + 1) // 2
        negative_count = k // 2
    elif k < 0:
        positive_count = (-k) // 2
        negative_count = (-k + 1) // 2
    else:
        positive_count = negative_count = 0
    return image, positive_count, negative_count


def generate_image_sources(
    room: Room,
    source: tuple[float, float, float],
    receiver: tuple[float, float, float],
    max_order: int = 8,
    c: float = 343.0,
) -> list[dict]:
    """Generate all rectangular-room images up to a *total* reflection order.

    Total order is ``|kx| + |ky| + |kz|``.  Order zero is the direct path and is
    always included, including when ``max_order`` is zero.  Distances, delays,
    and image coordinates are returned without display rounding.
    """
    if not isinstance(max_order, int) or isinstance(max_order, bool) or max_order < 0:
        raise ValueError("max_order must be a non-negative integer")
    if not isinstance(c, Real) or isinstance(c, bool) or not math.isfinite(c) or c <= 0:
        raise ValueError("c must be finite and positive")

    (sx, sy, sz), (rx, ry, rz) = validate_source_receiver(room, source, receiver)
    dimensions = (room.largo, room.ancho, room.alto)
    image_sources = []

    for px in range(-max_order, max_order + 1):
        for py in range(-max_order, max_order + 1):
            for pz in range(-max_order, max_order + 1):
                total_order = abs(px) + abs(py) + abs(pz)
                if total_order > max_order:
                    continue

                x_image, x_positive, x_negative = _image_position(sx, dimensions[0], px)
                y_image, y_positive, y_negative = _image_position(sy, dimensions[1], py)
                z_image, z_positive, z_negative = _image_position(sz, dimensions[2], pz)
                wall_counts = {
                    "x_min": x_negative,
                    "x_max": x_positive,
                    "y_min": y_negative,
                    "y_max": y_positive,
                    "z_min": z_negative,
                    "z_max": z_positive,
                }

                named_counts: dict[str, int] = {}
                for surface, wall_key in zip(room.superficies, WALL_KEYS):
                    named_counts[surface.nombre] = (
                        named_counts.get(surface.nombre, 0) + wall_counts[wall_key]
                    )

                dx = x_image - rx
                dy = y_image - ry
                dz = z_image - rz
                distance = math.sqrt(dx * dx + dy * dy + dz * dz)
                image_sources.append({
                    "position": (x_image, y_image, z_image),
                    "delay": distance / float(c),
                    "distance": distance,
                    "total_order": total_order,
                    "is_direct": total_order == 0,
                    "image_indices": (px, py, pz),
                    "reflection_counts": named_counts,
                    "wall_reflection_counts": wall_counts,
                    "reflection_counts_by_wall": wall_counts.copy(),
                })

    image_sources.sort(
        key=lambda item: (item["delay"], item["total_order"], item["image_indices"])
    )
    return image_sources


def _selected_bands(
    banda: Optional[str], bands: Optional[Iterable[str]],
) -> list[str]:
    if bands is None:
        selected = [banda] if banda is not None else list(BANDAS_OCTAVA)
    else:
        selected = list(dict.fromkeys(str(value) for value in bands))
        if banda is not None and banda not in selected:
            selected.insert(0, banda)
    if not selected:
        raise ValueError("at least one frequency band is required")
    unknown = [band for band in selected if band not in BANDAS_OCTAVA]
    if unknown:
        raise ValueError(f"unknown octave band(s): {', '.join(unknown)}")
    return selected


def calculate_energy(
    sources: list[dict],
    room: Room,
    banda: Optional[str] = None,
    *,
    bands: Optional[Iterable[str]] = None,
    source_amplitude: float = 1.0,
    phase_signs: Optional[dict[str, int]] = None,
) -> list[dict]:
    """Assign signed pressure amplitudes and squared pressure energy to images.

    Pressure follows ``source_amplitude / distance`` and each wall hit applies
    ``sqrt(1-alpha)``.  Since absorption contains no phase information, all
    reflections are positive by default.  ``phase_signs`` may map a canonical
    wall key (``x_min`` ... ``z_max``) or surface name to ``+1``/``-1``.

    The legacy ``banda`` argument still populates scalar ``amplitude`` and
    ``energy`` fields.  Passing ``bands`` (or omitting ``banda``) additionally
    provides ``amplitudes_by_band`` and ``energies_by_band``.
    """
    if (
        isinstance(source_amplitude, bool)
        or not isinstance(source_amplitude, Real)
        or not math.isfinite(source_amplitude)
    ):
        raise ValueError("source_amplitude must be finite")
    selected = _selected_bands(banda, bands)
    phase_signs = phase_signs or {}
    for wall, sign in phase_signs.items():
        if sign not in (-1, 1):
            raise ValueError(f"phase sign for {wall!r} must be +1 or -1")

    result = []
    for source in sources:
        distance = source.get("distance")
        if (
            isinstance(distance, bool)
            or not isinstance(distance, Real)
            or not math.isfinite(distance)
            or distance <= 0
        ):
            raise ValueError("every image source must have a positive finite distance")

        wall_counts = source.get("wall_reflection_counts")
        named_counts = source.get("reflection_counts", {})
        amplitudes: dict[str, float] = {}
        energies: dict[str, float] = {}
        coefficients_by_band: dict[str, dict[str, float]] = {}

        for band in selected:
            reflection_gain = 1.0
            wall_coefficients = {}
            for surface, wall_key in zip(room.superficies, WALL_KEYS):
                alpha = surface.material.alpha.get(band)
                if alpha is None:
                    raise ValueError(
                        f"surface {surface.nombre!r} has no absorption for band {band}"
                    )
                sign = phase_signs.get(wall_key, phase_signs.get(surface.nombre, 1))
                coefficient = sign * math.sqrt(max(0.0, 1.0 - alpha))
                wall_coefficients[wall_key] = coefficient
                if wall_counts is not None:
                    count = wall_counts.get(wall_key, 0)
                else:
                    count = named_counts.get(surface.nombre, 0)
                reflection_gain *= coefficient ** count

            amplitude = float(source_amplitude) * reflection_gain / float(distance)
            amplitudes[band] = amplitude
            energies[band] = amplitude * amplitude
            coefficients_by_band[band] = wall_coefficients

        enriched = source.copy()
        enriched["amplitudes_by_band"] = amplitudes
        enriched["energies_by_band"] = energies
        enriched["reflection_coefficients_by_band"] = coefficients_by_band
        enriched["spreading_model"] = "unit pressure at 1 m; pressure proportional to 1/r"
        enriched["reflection_phase_assumption"] = (
            "zero phase unless phase_signs specifies a pi phase shift"
        )
        legacy_band = banda if banda is not None else (selected[0] if len(selected) == 1 else None)
        if legacy_band is not None:
            enriched["band"] = legacy_band
            enriched["amplitude"] = amplitudes[legacy_band]
            enriched["energy"] = energies[legacy_band]
        # Preserve the legacy in-place enrichment as well as returning the list.
        source.update(enriched)
        result.append(source)
    return result


def _arrival_amplitude(source: dict, band: Optional[str]) -> float:
    if band is not None and band in source.get("amplitudes_by_band", {}):
        value = source["amplitudes_by_band"][band]
    elif "amplitude" in source:
        value = source["amplitude"]
    elif len(source.get("amplitudes_by_band", {})) == 1:
        value = next(iter(source["amplitudes_by_band"].values()))
    elif "energy" in source:
        energy = float(source["energy"])
        value = math.copysign(math.sqrt(abs(energy)), source.get("polarity", 1.0))
    elif source.get("distance", 0) > 0:
        value = 1.0 / float(source["distance"])
    else:
        value = 1.0
    if not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError("arrival amplitude must be finite")
    return float(value)


def build_impulse_response(
    sources: list[dict],
    fs: int = 44100,
    duration_s: float = 1.0,
    banda_energia: Optional[str] = None,
    room: Optional[Room] = None,
    *,
    fractional_delay: str = "linear",
    normalize: bool = False,
) -> dict:
    """Render arrivals as discrete pressure impulses.

    The default two-tap linear fractional-delay kernel splits a Dirac arrival
    between adjacent samples.  Unlike the former positive Gaussian, it has no
    arbitrary temporal width, preserves impulse area and preserves signed
    pressure.  ``fractional_delay='nearest'`` is available for a one-sample
    Kronecker impulse.  Physical amplitudes are not normalized unless requested.
    """
    del room  # Retained for call compatibility; amplitudes already describe walls.
    if not isinstance(fs, int) or isinstance(fs, bool) or fs <= 0:
        raise ValueError("fs must be a positive integer")
    if not isinstance(duration_s, Real) or not math.isfinite(duration_s) or duration_s <= 0:
        raise ValueError("duration_s must be finite and positive")
    if fractional_delay not in ("linear", "nearest"):
        raise ValueError("fractional_delay must be 'linear' or 'nearest'")

    sample_count = int(round(fs * duration_s))
    if sample_count <= 0:
        raise ValueError("duration_s is shorter than one sample")
    impulse_response = [0.0] * sample_count

    direct_sources = [
        source for source in sources
        if source.get("is_direct") or source.get("total_order") == 0
    ]
    direct_source = min(direct_sources or sources, key=lambda item: item["delay"], default=None)
    direct_delay = float(direct_source["delay"]) if direct_source is not None else 0.0

    arrivals_rendered = 0
    for source in sources:
        delay = source.get("delay")
        if (
            isinstance(delay, bool)
            or not isinstance(delay, Real)
            or not math.isfinite(delay)
            or delay < 0
        ):
            raise ValueError("arrival delay must be finite and non-negative")
        sample_position = float(delay) * fs
        amplitude = _arrival_amplitude(source, banda_energia)

        if fractional_delay == "nearest":
            sample_index = int(math.floor(sample_position + 0.5))
            if 0 <= sample_index < sample_count:
                impulse_response[sample_index] += amplitude
                arrivals_rendered += 1
            continue

        lower_index = int(math.floor(sample_position))
        fraction = sample_position - lower_index
        rendered = False
        if 0 <= lower_index < sample_count:
            impulse_response[lower_index] += amplitude * (1.0 - fraction)
            rendered = True
        if fraction > 0.0 and 0 <= lower_index + 1 < sample_count:
            impulse_response[lower_index + 1] += amplitude * fraction
            rendered = True
        arrivals_rendered += int(rendered)

    normalization_gain = 1.0
    if normalize and impulse_response:
        peak = max(abs(value) for value in impulse_response)
        if peak > 0:
            normalization_gain = 1.0 / peak
            impulse_response = [value * normalization_gain for value in impulse_response]

    return {
        "impulse_response": impulse_response,
        "sample_rate": fs,
        "direct_delay_ms": direct_delay * 1000.0,
        "direct_delay_s": direct_delay,
        "direct_sample": direct_delay * fs,
        "arrivals_rendered": arrivals_rendered,
        "impulse_representation": (
            "two-tap linear fractional-delay pressure impulse"
            if fractional_delay == "linear"
            else "nearest-sample Kronecker pressure impulse"
        ),
        "normalization_gain": normalization_gain,
        "band": banda_energia,
    }


def schroeder_integration(
    ir: list[float], fs: int, *, floor_db: float = -120.0,
) -> list[float]:
    """Return normalized reverse-integrated squared pressure in decibels."""
    if not isinstance(fs, int) or isinstance(fs, bool) or fs <= 0:
        raise ValueError("fs must be a positive integer")
    if floor_db >= 0 or not math.isfinite(floor_db):
        raise ValueError("floor_db must be finite and negative")
    if not ir:
        return []
    squared = []
    for value in ir:
        if not isinstance(value, Real) or not math.isfinite(value):
            raise ValueError("ir must contain only finite real samples")
        squared.append(float(value) * float(value))
    total_energy = sum(squared)
    if total_energy <= 0:
        return [floor_db] * len(ir)

    floor_ratio = 10.0 ** (floor_db / 10.0)
    decay = [floor_db] * len(ir)
    cumulative = 0.0
    for index in range(len(ir) - 1, -1, -1):
        cumulative += squared[index]
        decay[index] = 10.0 * math.log10(max(cumulative / total_energy, floor_ratio))
    decay[0] = 0.0
    return decay


def _regression_diagnostics(
    decay: list[float],
    fs: int,
    start_db: float,
    end_db: float,
) -> dict:
    # Values at the numerical integration floor after the final non-zero event
    # are not usable decay range (a direct-only IR therefore has 0 dB range).
    unfloored = [value for value in decay if value > -120.0 + 1e-9]
    available_range = max(0.0, -min(unfloored)) if unfloored else 0.0
    points = [
        (index / fs, value)
        for index, value in enumerate(decay)
        if start_db >= value >= end_db
    ]
    base = {
        "range_db": [start_db, end_db],
        "valid_dynamic_range_db": available_range,
        "sample_count": len(points),
        "slope_db_per_s": None,
        "intercept_db": None,
        "r2": None,
        "residual_rms_db": None,
        "max_residual_db": None,
        "nonlinearity_percent": None,
        "is_nonlinear": None,
        "rt60_s": None,
        "valid": False,
    }
    if len(points) < 3:
        base["reason"] = "fewer than three samples in regression range"
        return base

    count = len(points)
    mean_x = sum(point[0] for point in points) / count
    mean_y = sum(point[1] for point in points) / count
    sxx = sum((point[0] - mean_x) ** 2 for point in points)
    if sxx <= 0:
        base["reason"] = "zero regression time span"
        return base
    slope = sum(
        (point[0] - mean_x) * (point[1] - mean_y) for point in points
    ) / sxx
    intercept = mean_y - slope * mean_x
    residuals = [value - (slope * time + intercept) for time, value in points]
    residual_sum = sum(value * value for value in residuals)
    total_sum = sum((point[1] - mean_y) ** 2 for point in points)
    r2 = 1.0 - residual_sum / total_sum if total_sum > 0 else 1.0
    residual_rms = math.sqrt(residual_sum / count)
    max_residual = max(abs(value) for value in residuals)
    fitted_range = abs(start_db - end_db)
    nonlinearity = 100.0 * residual_rms / fitted_range if fitted_range else 0.0
    reaches_range = (
        max(decay) >= start_db - 0.1
        and available_range >= abs(end_db) - 0.1
    )
    valid = slope < 0 and reaches_range

    base.update({
        "slope_db_per_s": slope,
        "intercept_db": intercept,
        "r2": r2,
        "residual_rms_db": residual_rms,
        "max_residual_db": max_residual,
        "nonlinearity_percent": nonlinearity,
        "is_nonlinear": r2 < 0.9 or nonlinearity > 10.0,
        "rt60_s": -60.0 / slope if valid else None,
        "valid": valid,
        "reason": None if valid else "requested decay range is unavailable or non-decaying",
    })
    return base


def _linear_regression_db(
    decay: list[float],
    fs: int,
    start_db: float = -5,
    end_db: float = -35,
) -> float:
    """Legacy scalar RT60 extrapolation for a decay regression range."""
    result = _regression_diagnostics(decay, fs, start_db, end_db)
    return result["rt60_s"] if result["rt60_s"] is not None else 0.0


def normalized_autocorrelation(
    signal: list[float],
    max_lag: int,
    *,
    min_lag: int = 0,
    remove_mean: bool = True,
) -> list[float]:
    """Return biased autocorrelation normalized by zero-lag signal energy.

    The result covers every lag from ``min_lag`` through ``max_lag``.  Biased
    normalization avoids spuriously perfect values where only one pair overlaps.
    """
    if not isinstance(max_lag, int) or not isinstance(min_lag, int):
        raise ValueError("autocorrelation lags must be integers")
    if min_lag < 0 or max_lag < min_lag or max_lag >= len(signal):
        raise ValueError("autocorrelation lag range is outside the signal")
    if len(signal) * (max_lag - min_lag + 1) > 20_000_000:
        raise ValueError("autocorrelation input exceeds the bounded pure-Python limit")
    values = [float(value) for value in signal]
    if not all(math.isfinite(value) for value in values):
        raise ValueError("signal must contain finite samples")
    if remove_mean and values:
        mean = sum(values) / len(values)
        values = [value - mean for value in values]
    energy = sum(value * value for value in values)
    if energy <= 0:
        return [0.0] * (max_lag - min_lag + 1)
    return [
        sum(values[index] * values[index + lag] for index in range(len(values) - lag))
        / energy
        for lag in range(min_lag, max_lag + 1)
    ]


def detect_flutter_echo(
    signal: list[float],
    fs: int,
    *,
    start_sample: int = 0,
    min_delay_ms: float = 2.0,
    max_delay_ms: float = 50.0,
    threshold: float = 0.45,
) -> dict:
    """Detect a periodic echo train using normalized autocorrelation.

    A local autocorrelation peak must exceed ``threshold`` and the median
    sidelobe magnitude by 0.15.  The default 0.45 threshold is intentionally
    conservative.  Correlation magnitude is used so alternating-polarity echo
    trains remain detectable; ``polarity`` reports the peak sign.
    """
    if not isinstance(fs, int) or isinstance(fs, bool) or fs <= 0:
        raise ValueError("fs must be a positive integer")
    if not 0 < threshold <= 1:
        raise ValueError("threshold must be in (0, 1]")
    if min_delay_ms <= 0 or max_delay_ms <= min_delay_ms:
        raise ValueError("flutter delay bounds are invalid")
    if not 0 <= start_sample < max(1, len(signal)):
        raise ValueError("start_sample is outside the signal")

    segment = [float(value) for value in signal[start_sample:start_sample + int(0.5 * fs)]]
    if len(segment) < max(8, int(fs * max_delay_ms / 1000.0) + 2):
        return {
            "detected": False,
            "frequency": None,
            "period_ms": None,
            "correlation": 0.0,
            "polarity": None,
            "threshold": threshold,
            "reason": "insufficient analysis duration",
        }

    # Peak-preserving decimation bounds the stdlib autocorrelation cost while
    # retaining sparse positive and negative reflection events.
    decimation = max(1, math.ceil(fs / 4000))
    if decimation > 1:
        reduced = []
        for offset in range(0, len(segment), decimation):
            block = segment[offset:offset + decimation]
            reduced.append(max(block, key=abs))
        segment = reduced
    analysis_rate = fs / decimation
    min_lag = max(1, int(math.ceil(min_delay_ms * analysis_rate / 1000.0)))
    max_lag = min(
        int(math.floor(max_delay_ms * analysis_rate / 1000.0)),
        len(segment) // 4,
    )
    if max_lag <= min_lag:
        return {
            "detected": False,
            "frequency": None,
            "period_ms": None,
            "correlation": 0.0,
            "polarity": None,
            "threshold": threshold,
            "reason": "insufficient lag range",
        }

    correlation = normalized_autocorrelation(
        segment, max_lag, min_lag=min_lag, remove_mean=True,
    )
    magnitudes = [abs(value) for value in correlation]
    sorted_magnitudes = sorted(magnitudes)
    median = sorted_magnitudes[len(sorted_magnitudes) // 2]
    candidates = []
    for offset in range(1, len(correlation) - 1):
        magnitude = magnitudes[offset]
        if magnitude >= magnitudes[offset - 1] and magnitude >= magnitudes[offset + 1]:
            if magnitude >= threshold and magnitude - median >= 0.15:
                candidates.append((offset + min_lag, correlation[offset]))

    if not candidates:
        peak = max(magnitudes, default=0.0)
        return {
            "detected": False,
            "frequency": None,
            "period_ms": None,
            "correlation": peak,
            "polarity": None,
            "threshold": threshold,
            "median_sidelobe": median,
            "reason": "no prominent normalized-autocorrelation peak",
        }

    strongest = max(abs(value) for _, value in candidates)
    peak_lag, peak_value = next(
        item for item in candidates if abs(item[1]) >= 0.8 * strongest
    )
    return {
        "detected": True,
        "frequency": analysis_rate / peak_lag,
        "period_ms": peak_lag / analysis_rate * 1000.0,
        "correlation": abs(peak_value),
        "polarity": "positive" if peak_value >= 0 else "alternating",
        "threshold": threshold,
        "median_sidelobe": median,
        "analysis_sample_rate": analysis_rate,
        "reason": None,
    }


def _energy_ratio_db(numerator: float, denominator: float, floor: float) -> float:
    return 10.0 * math.log10(max(numerator, floor) / max(denominator, floor))


def _initial_time_delay_gap(
    ir: list[float], fs: int, direct_index: int,
) -> Optional[float]:
    absolute = [abs(value) for value in ir]
    direct_end = min(len(ir), direct_index + 2)
    local_direct_peak = max(absolute[direct_index:direct_end], default=0.0)
    threshold = local_direct_peak * 0.02
    if threshold <= 0:
        return None
    for index in range(direct_index + 2, len(ir)):
        previous = absolute[index - 1]
        following = absolute[index + 1] if index + 1 < len(ir) else -1.0
        if absolute[index] >= threshold and absolute[index] >= previous and absolute[index] > following:
            return (index - direct_index) / fs * 1000.0
    return None


def calculate_iso3382_parameters(
    ir: list[float],
    fs: int,
    direct_delay_ms: float = 0,
    *,
    metric_context: str = "predicted_model",
) -> dict:
    """Calculate direct-arrival-aligned ISO 3382-style room metrics.

    EDT uses 0 to -10 dB, T20 uses -5 to -25 dB, and T30 uses -5 to
    -35 dB.  These are regression extrapolations, not independently measured
    60 dB decays.  Every regression includes slope, R2, available dynamic range,
    and residual-based nonlinearity diagnostics.
    """
    if not isinstance(fs, int) or isinstance(fs, bool) or fs <= 0:
        raise ValueError("fs must be a positive integer")
    if not ir:
        return {"error": "Sin energia en la respuesta al impulso"}
    samples = [float(value) for value in ir]
    if not all(math.isfinite(value) for value in samples):
        raise ValueError("ir must contain only finite samples")
    total_input_energy = sum(value * value for value in samples)
    if total_input_energy <= 0:
        return {"error": "Sin energia en la respuesta al impulso"}
    if not isinstance(direct_delay_ms, Real) or not math.isfinite(direct_delay_ms):
        raise ValueError("direct_delay_ms must be finite")
    if direct_delay_ms < 0:
        raise ValueError("direct_delay_ms must be non-negative")

    if direct_delay_ms > 0:
        direct_index = int(math.floor(direct_delay_ms * fs / 1000.0))
        if direct_index >= len(samples):
            raise ValueError("direct arrival lies outside the impulse response")
    else:
        onset_threshold = max(abs(value) for value in samples) * 1e-8
        direct_index = next(
            (index for index, value in enumerate(samples) if abs(value) > onset_threshold),
            0,
        )

    aligned = samples[direct_index:]
    squared = [value * value for value in aligned]
    total_energy = sum(squared)
    decay = schroeder_integration(aligned, fs)
    regressions = {
        "EDT": _regression_diagnostics(decay, fs, 0.0, -10.0),
        "T20": _regression_diagnostics(decay, fs, -5.0, -25.0),
        "T30": _regression_diagnostics(decay, fs, -5.0, -35.0),
    }
    valid_dynamic_range = max(
        diagnostic["valid_dynamic_range_db"] for diagnostic in regressions.values()
    )

    samples_50 = min(len(squared), int(round(0.050 * fs)))
    samples_80 = min(len(squared), int(round(0.080 * fs)))
    early_50 = sum(squared[:samples_50])
    early_80 = sum(squared[:samples_80])
    late_50 = total_energy - early_50
    late_80 = total_energy - early_80
    numerical_floor = max(total_energy * 1e-15, 1e-300)
    c50 = _energy_ratio_db(early_50, late_50, numerical_floor)
    c80 = _energy_ratio_db(early_80, late_80, numerical_floor)
    d50 = 100.0 * early_50 / total_energy
    center_time_ms = (
        sum(index / fs * energy for index, energy in enumerate(squared))
        / total_energy * 1000.0
    )
    itdg = _initial_time_delay_gap(samples, fs, direct_index)
    flutter_start = min(len(samples) - 1, direct_index + max(2, int(0.002 * fs)))
    flutter = detect_flutter_echo(samples, fs, start_sample=flutter_start)

    scalar_metrics = {
        "EDT": regressions["EDT"]["rt60_s"],
        "T20": regressions["T20"]["rt60_s"],
        "T30": regressions["T30"]["rt60_s"],
        "C80": c80,
        "C50": c50,
        "D50": d50,
        "Ts": center_time_ms,
        "ITDG": itdg,
    }
    return {
        **scalar_metrics,
        "flutter_echo": flutter,
        "regression_diagnostics": regressions,
        "valid_dynamic_range_db": valid_dynamic_range,
        "direct_arrival_ms": direct_index / fs * 1000.0,
        "direct_arrival_sample": direct_index,
        "metric_context": metric_context,
        "predicted_model_metrics": scalar_metrics.copy() if metric_context == "predicted_model" else None,
        "method": "ISO 3382-style decay and energy metrics aligned to direct arrival",
        "energy_ratio_floor_db": -150.0,
    }

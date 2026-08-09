"""Frequency-resolved wave/geometric hybridization utilities.

This module blends spectra, not scalar reverberation times.  A complementary
raised-cosine window in log-frequency crosses at the Schroeder frequency.  The
low-frequency method is image source for a declared shoebox and FEM for polygonal
or arbitrary geometry; callers provide the corresponding computed response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class FrequencyResponse:
    frequencies_hz: Sequence[float]
    values: Sequence[complex | float]
    method: str
    quantity: str = "energy"
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        frequencies = np.asarray(self.frequencies_hz, dtype=float)
        values = np.asarray(self.values)
        if frequencies.ndim != 1 or len(frequencies) == 0:
            raise ValueError("frequencies_hz must be a non-empty one-dimensional sequence")
        if values.shape != frequencies.shape:
            raise ValueError("response values must match frequencies_hz")
        if np.any(frequencies <= 0.0) or not np.all(np.isfinite(frequencies)):
            raise ValueError("frequencies_hz must be positive and finite")
        if np.any(np.diff(frequencies) <= 0.0):
            raise ValueError("frequencies_hz must be strictly increasing")
        if not np.all(np.isfinite(values)):
            raise ValueError("response values must be finite")
        if not self.method:
            raise ValueError("response method must not be empty")
        object.__setattr__(self, "frequencies_hz", frequencies)
        object.__setattr__(self, "values", values)


@dataclass(frozen=True)
class HybridResult:
    frequencies_hz: np.ndarray
    low_frequency: FrequencyResponse
    high_frequency: FrequencyResponse
    combined_values: np.ndarray
    low_weights: np.ndarray
    high_weights: np.ndarray
    schroeder_frequency_hz: float
    crossover_octaves: float
    low_method: str
    high_method: str
    research_status: str

    def to_dict(self) -> dict:
        def serializable_values(values: np.ndarray) -> list[float] | dict[str, list[float]]:
            if np.iscomplexobj(values) and np.any(np.abs(np.imag(values)) > 1e-14):
                return {
                    "real": np.real(values).astype(float).tolist(),
                    "imag": np.imag(values).astype(float).tolist(),
                }
            return np.real(values).astype(float).tolist()

        return {
            "frequencies_hz": self.frequencies_hz.tolist(),
            "low_frequency": {
                "method": self.low_method,
                "quantity": self.low_frequency.quantity,
                "values": serializable_values(np.asarray(self.low_frequency.values)),
            },
            "high_frequency": {
                "method": self.high_method,
                "quantity": self.high_frequency.quantity,
                "values": serializable_values(np.asarray(self.high_frequency.values)),
            },
            "combined_values": serializable_values(self.combined_values),
            "low_weights": self.low_weights.tolist(),
            "high_weights": self.high_weights.tolist(),
            "schroeder_frequency_hz": self.schroeder_frequency_hz,
            "crossover_octaves": self.crossover_octaves,
            "research_status": self.research_status,
        }


def schroeder_frequency_hz(rt60_s: float, volume_m3: float) -> float:
    """Return the conventional statistical estimate ``2000 sqrt(T60 / V)``."""

    if rt60_s < 0.0 or volume_m3 <= 0.0:
        raise ValueError("rt60_s must be non-negative and volume_m3 positive")
    return 2000.0 * math.sqrt(rt60_s / volume_m3)


def choose_low_frequency_method(geometry: str | Mapping[str, object]) -> str:
    """Choose ``ism`` only for declared rectangular shoebox geometry."""

    if isinstance(geometry, Mapping):
        geometry_name = str(geometry.get("kind", geometry.get("type", "arbitrary")))
    else:
        geometry_name = str(geometry)
    normalized = geometry_name.strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"shoebox", "rectangular", "rectangular_room", "cuboid", "box"}:
        return "ism"
    return "fem"


def complementary_crossover_weights(
    frequencies_hz: Sequence[float],
    schroeder_hz: float,
    crossover_octaves: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return complementary low/high raised-cosine weights in log frequency."""

    frequencies = np.asarray(frequencies_hz, dtype=float)
    if frequencies.ndim != 1 or len(frequencies) == 0 or np.any(frequencies <= 0.0):
        raise ValueError("frequencies_hz must contain positive frequencies")
    if schroeder_hz <= 0.0 or crossover_octaves <= 0.0:
        raise ValueError("schroeder_hz and crossover_octaves must be positive")
    normalized_position = np.log2(frequencies / schroeder_hz) / crossover_octaves + 0.5
    window_position = np.clip(normalized_position, 0.0, 1.0)
    high = 0.5 - 0.5 * np.cos(math.pi * window_position)
    low = 1.0 - high
    return low, high


def _interpolate_response(response: FrequencyResponse, frequencies_hz: np.ndarray) -> np.ndarray:
    source_log_frequency = np.log(np.asarray(response.frequencies_hz, dtype=float))
    target_log_frequency = np.log(frequencies_hz)
    values = np.asarray(response.values)
    if np.iscomplexobj(values):
        real = np.interp(target_log_frequency, source_log_frequency, np.real(values))
        imaginary = np.interp(target_log_frequency, source_log_frequency, np.imag(values))
        return real + 1j * imaginary
    return np.interp(target_log_frequency, source_log_frequency, values.astype(float))


def hybridize_frequency_responses(
    *,
    high_frequency_response: FrequencyResponse,
    schroeder_hz: float,
    geometry: str | Mapping[str, object],
    ism_response: FrequencyResponse | None = None,
    fem_response: FrequencyResponse | None = None,
    frequencies_hz: Sequence[float] | None = None,
    crossover_octaves: float = 1.0,
) -> HybridResult:
    """Select the low solver and blend it with a geometric high response."""

    low_method = choose_low_frequency_method(geometry)
    low_response = ism_response if low_method == "ism" else fem_response
    if low_response is None:
        raise ValueError(f"geometry requires a {low_method.upper()} low-frequency response")
    if low_response.quantity != high_frequency_response.quantity:
        raise ValueError("low- and high-frequency responses must represent the same quantity")
    if frequencies_hz is None:
        frequencies = np.unique(
            np.concatenate(
                [
                    np.asarray(low_response.frequencies_hz, dtype=float),
                    np.asarray(high_frequency_response.frequencies_hz, dtype=float),
                ]
            )
        )
    else:
        frequencies = np.asarray(frequencies_hz, dtype=float)
        if (
            frequencies.ndim != 1
            or len(frequencies) == 0
            or not np.all(np.isfinite(frequencies))
            or np.any(frequencies <= 0.0)
            or np.any(np.diff(frequencies) <= 0.0)
        ):
            raise ValueError("frequencies_hz must be a positive, finite, strictly increasing sequence")
    low_values = _interpolate_response(low_response, frequencies)
    high_values = _interpolate_response(high_frequency_response, frequencies)
    low_weights, high_weights = complementary_crossover_weights(
        frequencies,
        schroeder_hz,
        crossover_octaves,
    )
    combined = low_weights * low_values + high_weights * high_values
    selected_low = FrequencyResponse(
        frequencies_hz=frequencies,
        values=low_values,
        method=low_method,
        quantity=low_response.quantity,
        metadata=low_response.metadata,
    )
    selected_high = FrequencyResponse(
        frequencies_hz=frequencies,
        values=high_values,
        method=high_frequency_response.method,
        quantity=high_frequency_response.quantity,
        metadata=high_frequency_response.metadata,
    )
    return HybridResult(
        frequencies_hz=frequencies,
        low_frequency=selected_low,
        high_frequency=selected_high,
        combined_values=np.asarray(combined),
        low_weights=low_weights,
        high_weights=high_weights,
        schroeder_frequency_hz=float(schroeder_hz),
        crossover_octaves=float(crossover_octaves),
        low_method=low_method,
        high_method=high_frequency_response.method,
        research_status=(
            "Research spectral crossover. ISM is selected only for a declared shoebox; "
            "arbitrary geometry requires FEM below crossover and ray transport above it."
        ),
    )


# Short alias for callers that use the result as a construction primitive.
build_hybrid_result = hybridize_frequency_responses


__all__ = [
    "FrequencyResponse",
    "HybridResult",
    "build_hybrid_result",
    "choose_low_frequency_method",
    "complementary_crossover_weights",
    "hybridize_frequency_responses",
    "schroeder_frequency_hz",
]

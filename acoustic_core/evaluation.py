"""Modal-distribution and transition-frequency evaluation helpers."""

from __future__ import annotations

import math

from .models import Mode, ModeType
from .spectrum import THIRD_OCTAVE_BANDS


def _finite_input(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def calculate_schroeder(rt60_sabine: float, volumen: float) -> float:
    rt60 = _finite_input(rt60_sabine, "rt60_sabine")
    volume = _finite_input(volumen, "volumen")
    if rt60 <= 0.0 or volume <= 0.0:
        return 0.0
    result = 2000.0 * math.sqrt(rt60 / volume)
    if not math.isfinite(result):
        raise OverflowError("Schroeder frequency exceeds finite floating-point range")
    return result


def calculate_modal_bandwidth(rt60_sabine: float) -> float:
    rt60 = _finite_input(rt60_sabine, "rt60_sabine")
    if rt60 <= 0.0:
        return 0.0
    result = 2.2 / rt60
    if not math.isfinite(result):
        raise OverflowError("modal bandwidth exceeds finite floating-point range")
    return result


def evaluate_bonello(frecuencias: list[float]) -> dict:
    """Count modes in proper one-third-octave bands and apply Bonello.

    Exact geometric band edges are lower-inclusive and upper-exclusive.  The
    result shape intentionally remains compatible with the existing API.
    """

    counts = [0] * len(THIRD_OCTAVE_BANDS)
    edge_ratio = 2.0 ** (1.0 / 6.0)
    edges = tuple(
        (center / edge_ratio, center * edge_ratio)
        for center in THIRD_OCTAVE_BANDS.exact_centers_hz
    )

    for raw_frequency in frecuencias:
        frequency = _finite_input(raw_frequency, "modal frequency")
        if frequency < 0.0:
            raise ValueError("modal frequencies must be non-negative")
        for index, (lower, upper) in enumerate(edges):
            if lower <= frequency < upper:
                counts[index] += 1
                break

    base_last_index = max(
        index
        for index, center in enumerate(THIRD_OCTAVE_BANDS.centers_hz)
        if center < 500.0
    )
    occupied_indices = [index for index, count in enumerate(counts) if count]
    last_index = max([base_last_index, *occupied_indices])
    resultado = {
        float(center): counts[index]
        for index, center in enumerate(THIRD_OCTAVE_BANDS.centers_hz[: last_index + 1])
    }

    band_counts = list(resultado.values())
    violaciones = [
        index
        for index in range(1, len(band_counts))
        if band_counts[index] < band_counts[index - 1]
    ]
    return {
        "cumple": not violaciones,
        "bandas": resultado,
        "violaciones": violaciones,
        "total_modos": sum(band_counts),
    }


def find_degenerate_dimensions(
    largo: float,
    ancho: float,
    alto: float,
    *,
    equality_tolerance_m: float = 0.01,
    ratio_tolerance: float = 0.01,
) -> list[str]:
    dimensions = [
        ("Largo", _finite_input(largo, "largo")),
        ("Ancho", _finite_input(ancho, "ancho")),
        ("Alto", _finite_input(alto, "alto")),
    ]
    if any(value <= 0.0 for _, value in dimensions):
        raise ValueError("room dimensions must be positive")
    if equality_tolerance_m < 0.0 or not math.isfinite(equality_tolerance_m):
        raise ValueError("equality_tolerance_m must be finite and non-negative")
    if ratio_tolerance < 0.0 or not math.isfinite(ratio_tolerance):
        raise ValueError("ratio_tolerance must be finite and non-negative")

    advertencias: list[str] = []
    for first_index, (first_name, first_value) in enumerate(dimensions):
        for second_name, second_value in dimensions[first_index + 1 :]:
            if abs(first_value - second_value) <= equality_tolerance_m:
                advertencias.append(
                    f"{first_name} ≈ {second_name} ({first_value:.2f} m): "
                    "dimensiones iguales -> alta degeneración modal"
                )
                continue

            if first_value > second_value:
                larger_name, larger = first_name, first_value
                smaller_name, smaller = second_name, second_value
            else:
                larger_name, larger = second_name, second_value
                smaller_name, smaller = first_name, first_value
            ratio = larger / smaller
            integer_ratio = round(ratio)
            if integer_ratio >= 2 and abs(ratio - integer_ratio) <= ratio_tolerance:
                advertencias.append(
                    f"{larger_name} es múltiplo entero de {smaller_name} "
                    f"({integer_ratio}x): puede causar modos degenerados"
                )
    return advertencias


def assess_diffuse_field(modos: list[Mode], minimum_overlap: int = 3) -> dict:
    """Assess the diffuse-field overlap threshold described by Schroeder."""

    if isinstance(minimum_overlap, bool) or not isinstance(minimum_overlap, int):
        raise TypeError("minimum_overlap must be an integer")
    if minimum_overlap < 2:
        raise ValueError("minimum_overlap must be at least two")
    maximum = max((mode.overlap_multiplicity for mode in modos), default=0)
    qualifying = sorted(
        {
            mode.overlap_cluster
            for mode in modos
            if mode.overlap_cluster is not None
            and mode.overlap_multiplicity >= minimum_overlap
        }
    )
    is_diffuse = maximum >= minimum_overlap
    return {
        "campo_difuso": is_diffuse,
        "umbral_solapamiento": minimum_overlap,
        "solapamiento_maximo": maximum,
        "clusters_difusos": qualifying,
        "is_diffuse": is_diffuse,
        "minimum_overlap": minimum_overlap,
        "max_overlap": maximum,
    }


evaluate_diffuse_field = assess_diffuse_field


def get_mode_distribution(modos: list[Mode]) -> dict:
    tipos = {mode_type: 0 for mode_type in ModeType}
    for mode in modos:
        tipos[mode.tipo] += 1
    diffuse = assess_diffuse_field(modos)
    return {
        "axiales": tipos[ModeType.AXIAL],
        "tangenciales": tipos[ModeType.TANGENTIAL],
        "oblicuos": tipos[ModeType.OBLIQUE],
        "degenerados": sum(1 for mode in modos if mode.degenerado),
        "solapados": sum(1 for mode in modos if mode.solapado),
        "solapamiento_maximo": diffuse["solapamiento_maximo"],
        "campo_difuso": diffuse["campo_difuso"],
    }

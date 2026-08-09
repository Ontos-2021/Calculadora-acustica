"""Legacy shoebox adapter for frequency-resolved numerical hybridization."""

from __future__ import annotations

import math

from .evaluation import calculate_schroeder
from .impulse import build_impulse_response, calculate_energy, calculate_iso3382_parameters, generate_image_sources
from .models import BANDAS_OCTAVA, Room
from .ray_tracing import trace_rays
from .resonance import calculate_modes
from .reverberation import rt60_sabine


C = 343.0


def _hybrid_api():
    try:
        from acoustic_numerics.hybrid import FrequencyResponse, hybridize_frequency_responses
    except ImportError as exc:
        raise RuntimeError("hybrid numerical analysis is server-only and requires NumPy and SciPy") from exc
    return FrequencyResponse, hybridize_frequency_responses


def _image_source_band_energy(
    room: Room,
    image_sources: list[dict],
    source: tuple[float, float, float],
    receiver: tuple[float, float, float],
    band: str,
) -> float:
    direct_distance = math.dist(source, receiver)
    total = 0.0
    if direct_distance > 0.0:
        total += 1.0 / (4.0 * math.pi * direct_distance**2)
    for image in image_sources:
        distance = float(image["distance"])
        if distance <= 0.0:
            continue
        reflected_energy = 1.0
        for surface in room.superficies:
            count = image["reflection_counts"].get(surface.nombre, 0)
            if count:
                reflected_energy *= (1.0 - surface.material.alpha.get(band, 0.0)) ** count
        total += reflected_energy / (4.0 * math.pi * distance**2)
    return total


def hybrid_analysis(
    room: Room,
    source: tuple[float, float, float] = (1, 1, 1.5),
    receiver: tuple[float, float, float] = (4, 3, 1.2),
    num_rays: int = 300,
    max_ism_order: int = 6,
    *,
    seed: int = 0,
    crossover_octaves: float = 1.0,
) -> dict:
    """Compute ISM/ray spectra and blend them around the Schroeder frequency.

    The legacy ``hybrid.rt60_estimate_s`` is retained for the existing UI, but it
    is selected from a valid estimator rather than formed by scalar RT averaging.
    The actual hybrid result is the complementary frequency response.
    """

    FrequencyResponse, hybridize_frequency_responses = _hybrid_api()
    rt60 = rt60_sabine(room, "500")
    if not math.isfinite(rt60) or rt60 <= 0.0:
        rt60 = 0.5
    f_sch = calculate_schroeder(rt60, room.volumen)
    if f_sch <= 0.0:
        f_sch = 1.0

    modes = calculate_modes(room, max_order=5)
    modal_frequencies = [mode.frecuencia for mode in modes]

    image_sources = generate_image_sources(room, source, receiver, max_order=max_ism_order)
    low_energy = [
        _image_source_band_energy(room, image_sources, source, receiver, band)
        for band in BANDAS_OCTAVA
    ]
    energy_sources_500 = calculate_energy(image_sources, room, "500")
    ism_ir = build_impulse_response(energy_sources_500, fs=44100, duration_s=0.5, room=room)
    ism_parameters = calculate_iso3382_parameters(
        ism_ir["impulse_response"],
        44100,
        ism_ir["direct_delay_ms"],
    )

    ray_result = trace_rays(
        room,
        source,
        receiver,
        num_rays=num_rays,
        max_reflections=30,
        max_time_s=0.5,
        seed=seed,
        bands_hz=[float(band) for band in BANDAS_OCTAVA],
    )
    high_energy = [
        float(ray_result["total_energy_by_band"].get(band, 0.0))
        for band in BANDAS_OCTAVA
    ]
    frequencies = [float(band) for band in BANDAS_OCTAVA]
    ism_response = FrequencyResponse(frequencies, low_energy, method="ism", quantity="energy")
    ray_response = FrequencyResponse(frequencies, high_energy, method="ray_tracing", quantity="energy")
    spectral_result = hybridize_frequency_responses(
        high_frequency_response=ray_response,
        schroeder_hz=f_sch,
        geometry="shoebox",
        ism_response=ism_response,
        frequencies_hz=frequencies,
        crossover_octaves=crossover_octaves,
    )
    spectral_payload = spectral_result.to_dict()

    reference_index = min(range(len(frequencies)), key=lambda index: abs(frequencies[index] - 500.0))
    legacy_rt60 = float(ray_result.get("rt60_estimate_s", 0.0))
    if legacy_rt60 <= 0.0:
        legacy_rt60 = float(ism_parameters.get("T20", 0.0) or 0.0)

    return {
        "schroeder_frequency_hz": f_sch,
        "modal_count_below_schroeder": sum(1 for frequency in modal_frequencies if frequency <= f_sch),
        "ism": {
            "image_sources": len(image_sources),
            "max_order": max_ism_order,
            "iso_3382": ism_parameters,
            "frequency_energy": dict(zip(BANDAS_OCTAVA, low_energy, strict=True)),
        },
        "ray_tracing": {
            "num_rays": num_rays,
            "energy_time_s": ray_result.get("energy_time_s", []),
            "energy_db": ray_result.get("energy_db", []),
            "rt60_estimate_s": ray_result.get("rt60_estimate_s", 0.0),
            "frequency_energy": dict(zip(BANDAS_OCTAVA, high_energy, strict=True)),
        },
        "low_frequency": spectral_payload["low_frequency"],
        "high_frequency": spectral_payload["high_frequency"],
        "frequency_response": spectral_payload,
        "hybrid": {
            "rt60_estimate_s": legacy_rt60,
            "rt60_note": "Legacy display value selected from ray T20/ISM T20; it is not blended.",
            "weight_ism": float(spectral_result.low_weights[reference_index]),
            "weight_ray_tracing": float(spectral_result.high_weights[reference_index]),
            "frequencies_hz": frequencies,
            "energy": spectral_payload["combined_values"],
        },
        "research_status": spectral_result.research_status,
    }

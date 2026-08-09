"""Shoebox compatibility wrapper for server-only geometric ray tracing."""

from __future__ import annotations

from typing import Mapping, Sequence

from .models import BANDAS_OCTAVA, Room


C = 343.0


def _numerical_api():
    try:
        from acoustic_numerics.ray_tracing import BandMaterial, RayTraceConfig, shoebox_scene, trace_scene
    except ImportError as exc:
        raise RuntimeError("ray tracing is server-only and requires NumPy and SciPy") from exc
    return BandMaterial, RayTraceConfig, shoebox_scene, trace_scene


def trace_rays(
    room: Room,
    source: tuple[float, float, float],
    receiver: tuple[float, float, float],
    num_rays: int = 500,
    max_reflections: int = 50,
    max_time_s: float = 1.0,
    *,
    seed: int = 0,
    bands_hz: Sequence[float] | None = None,
    listener_radius_m: float = 0.15,
    scattering: float | Mapping[str, float] = 0.0,
) -> dict:
    """Trace a deterministic shoebox response while preserving legacy keys."""

    BandMaterial, RayTraceConfig, shoebox_scene, trace_scene = _numerical_api()
    selected_bands = BANDAS_OCTAVA if bands_hz is None else bands_hz
    bands = tuple(float(band) for band in selected_bands)
    materials = []
    surface_ids = []
    for surface in room.superficies:
        if isinstance(scattering, Mapping):
            scatter_value = float(scattering.get(surface.nombre, scattering.get("default", 0.0)))
        else:
            scatter_value = float(scattering)
        materials.append(BandMaterial(absorption=surface.material.alpha, scattering=scatter_value))
        surface_ids.append(surface.nombre)
    scene = shoebox_scene(
        (room.largo, room.ancho, room.alto),
        materials=materials,
        surface_ids=surface_ids,
    )
    config = RayTraceConfig(
        bands_hz=bands,
        num_rays=num_rays,
        max_reflections=max_reflections,
        max_time_s=max_time_s,
        listener_radius_m=listener_radius_m,
        sound_speed_m_s=C,
        seed=seed,
    )
    result = trace_scene(scene, source, receiver, config)
    rich = result.to_dict()
    occupied_indices = [
        index
        for index in range(len(result.times_s))
        if any(result.energy_by_band[band_index, index] > 0.0 for band_index in range(len(result.bands_hz)))
    ]
    reference_band_index = min(
        range(len(result.bands_hz)),
        key=lambda index: abs(float(result.bands_hz[index]) - 500.0),
    )
    reference_rt60 = float(result.rt60_s_by_band[reference_band_index])
    rich.update(
        {
            "num_rays": num_rays,
            "energy_time_s": [float(result.times_s[index]) for index in occupied_indices],
            "energy_db": [float(result.energy_db_by_band[reference_band_index, index]) for index in occupied_indices],
            "rt60_estimate_s": reference_rt60,
            "method": "geometric acoustics with exact segment listener capture and next-event estimation",
        }
    )
    return rich

from .models import Room, BANDAS_OCTAVA
from .resonance import calculate_modes
from .reverberation import rt60_sabine
from .evaluation import calculate_schroeder
from .impulse import generate_image_sources, calculate_energy, build_impulse_response, calculate_iso3382_parameters
from .ray_tracing import trace_rays
from .pressure import compute_pressure_map

C = 343.0


def hybrid_analysis(
    room: Room,
    source: tuple[float, float, float] = (1, 1, 1.5),
    receiver: tuple[float, float, float] = (4, 3, 1.2),
    num_rays: int = 300,
    max_ism_order: int = 6,
) -> dict:
    rt60 = rt60_sabine(room, "500")
    if rt60 == float('inf'):
        rt60 = 0.5
    f_sch = calculate_schroeder(rt60, room.volumen)

    modos = calculate_modes(room, max_order=5)
    modal_freqs = [m.frecuencia for m in modos]

    ism_sources = generate_image_sources(room, source, receiver, max_order=max_ism_order)
    ism_sources = calculate_energy(ism_sources, room, "500")
    ism_ir = build_impulse_response(ism_sources, fs=44100, duration_s=0.5, room=room)
    ism_params = calculate_iso3382_parameters(ism_ir["impulse_response"], 44100, ism_ir["direct_delay_ms"])

    ray_result = trace_rays(room, source, receiver, num_rays=num_rays, max_reflections=30, max_time_s=0.5)

    hybrid_rt60 = 0
    if ism_params.get("T20", 0) > 0 and ray_result.get("rt60_estimate_s", 0) > 0:
        w_ism = max(0, min(1, 1 - f_sch / 1000))
        w_ray = 1 - w_ism
        hybrid_rt60 = round(w_ism * ism_params["T20"] + w_ray * ray_result["rt60_estimate_s"], 3)
    elif ism_params.get("T20", 0) > 0:
        hybrid_rt60 = round(ism_params["T20"], 3)
    else:
        hybrid_rt60 = round(ray_result.get("rt60_estimate_s", 0), 3)

    return {
        "schroeder_frequency_hz": round(f_sch, 1),
        "modal_count_below_schroeder": sum(1 for f in modal_freqs if f <= f_sch),
        "ism": {
            "image_sources": len(ism_sources),
            "max_order": max_ism_order,
            "iso_3382": ism_params,
        },
        "ray_tracing": {
            "num_rays": num_rays,
            "energy_time_s": ray_result.get("energy_time_s", []),
            "energy_db": ray_result.get("energy_db", []),
            "rt60_estimate_s": ray_result.get("rt60_estimate_s", 0),
        },
        "hybrid": {
            "rt60_estimate_s": hybrid_rt60,
            "weight_ism": round(max(0, min(1, 1 - f_sch / 1000)), 3),
            "weight_ray_tracing": round(min(1, f_sch / 1000), 3),
        },
    }

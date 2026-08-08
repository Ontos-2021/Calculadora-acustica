import math
import random
from .models import Room, BANDAS_OCTAVA

C = 343.0


def _normalize(v):
    mag = math.sqrt(v[0]**2 + v[1]**2 + v[2]**2)
    if mag == 0:
        return (0, 0, 0)
    return (v[0]/mag, v[1]/mag, v[2]/mag)


def _random_direction() -> tuple[float, float, float]:
    theta = random.random() * 2 * math.pi
    phi = math.acos(2 * random.random() - 1)
    return (math.sin(phi) * math.cos(theta),
            math.sin(phi) * math.sin(theta),
            math.cos(phi))


def _reflect(d: tuple[float, float, float], normal: tuple[float, float, float]) -> tuple[float, float, float]:
    dot = d[0]*normal[0] + d[1]*normal[1] + d[2]*normal[2]
    return (d[0] - 2*dot*normal[0],
            d[1] - 2*dot*normal[1],
            d[2] - 2*dot*normal[2])


def _ray_plane_intersect(origin, direction, plane_axis, plane_val):
    if direction[plane_axis] == 0:
        return None
    t = (plane_val - origin[plane_axis]) / direction[plane_axis]
    if t <= 0:
        return None
    hit = (origin[0] + t*direction[0],
           origin[1] + t*direction[1],
           origin[2] + t*direction[2])
    return (hit, t)


def _in_bounds(hit, dims, axis1, axis2):
    return 0 <= hit[axis1] <= dims[axis1] and 0 <= hit[axis2] <= dims[axis2]


def trace_rays(
    room: Room,
    source: tuple[float, float, float],
    receiver: tuple[float, float, float],
    num_rays: int = 500,
    max_reflections: int = 50,
    max_time_s: float = 1.0,
) -> dict:
    L, W, H = room.largo, room.ancho, room.alto
    planes = [
        ((0, 0, -1), 0, 0, 1, 2),
        ((0, 0, 1), H, 0, 1, 2),
        ((-1, 0, 0), 0, 1, 2, 1),
        ((1, 0, 0), L, 1, 2, 1),
        ((0, -1, 0), 0, 0, 2, 0),
        ((0, 1, 0), W, 0, 2, 0),
    ]
    energy_hist = {}
    dt = 0.01
    total_rays = 0

    for _ in range(num_rays):
        dir = _random_direction()
        pos = source
        energy = 1.0
        time = 0.0
        ray_alive = True
        for _r in range(max_reflections):
            if not ray_alive or time > max_time_s:
                break
            best_t = float('inf')
            best_hit = None
            best_normal = None
            best_plane = None
            for (n, val, ax1, ax2, ax3) in planes:
                axis = 0 if n[0] != 0 else (1 if n[1] != 0 else 2)
                result = _ray_plane_intersect(pos, dir, axis, val)
                if result:
                    hit, t = result
                    if 0 < t < best_t and _in_bounds(hit, (L, W, H), ax1, ax2):
                        best_t = t
                        best_hit = hit
                        best_normal = n
                        best_plane = (axis, val, ax1, ax2)

            if best_hit is None:
                ray_alive = False
                continue

            time += best_t / C
            total_rays += 1

            dist_to_rec = math.sqrt(sum((best_hit[i] - receiver[i])**2 for i in range(3)))
            if dist_to_rec < 0.5 and time <= max_time_s:
                time_key = round(time / dt) * dt
                energy_hist[time_key] = energy_hist.get(time_key, 0) + energy

            if best_normal:
                dir = _reflect(dir, best_normal)

            pos = best_hit
            surface_idx = best_plane[0] if best_plane else 0
            if surface_idx < len(room.superficies):
                alpha = room.superficies[surface_idx].material.alpha.get("500", 0.1)
                energy *= (1 - alpha)
            else:
                energy *= 0.9

            if energy < 0.001:
                break

    times = sorted(energy_hist.keys())
    energies = [energy_hist[t] for t in times]

    if energies:
        peak = max(energies)
        energies_db = [20 * math.log10(e / peak) if e > 0 else -60 for e in energies]
    else:
        energies_db = []

    rt60 = 0
    if len(energies_db) > 5:
        db5 = -5
        db25 = -25
        t5 = t25 = None
        for i in range(len(energies_db) - 1):
            if energies_db[i] >= db5 >= energies_db[i+1]:
                frac = (db5 - energies_db[i]) / (energies_db[i+1] - energies_db[i]) if energies_db[i+1] != energies_db[i] else 0
                t5 = times[i] + frac * (times[i+1] - times[i])
            if energies_db[i] >= db25 >= energies_db[i+1]:
                frac = (db25 - energies_db[i]) / (energies_db[i+1] - energies_db[i]) if energies_db[i+1] != energies_db[i] else 0
                t25 = times[i] + frac * (times[i+1] - times[i])
        if t5 and t25 and (t25 - t5) > 0:
            rt60 = round(6 * (t25 - t5) / 20, 3)

    return {
        "num_rays": num_rays,
        "total_ray_segments": total_rays,
        "energy_time_s": [round(t, 3) for t in times],
        "energy_db": [round(e, 2) for e in energies_db],
        "rt60_estimate_s": rt60,
    }

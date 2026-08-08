from .models import Room, BANDAS_OCTAVA
from .presets import MATERIALES_PRESETS, search_materials
from .design import get_rt60_target


def required_absorption(volume: float, rt60_target: dict[str, float]) -> dict[str, float]:
    result = {}
    for b in BANDAS_OCTAVA:
        t = rt60_target.get(b, 0.5)
        if t <= 0:
            result[b] = float('inf')
        else:
            result[b] = round(0.161 * volume / t, 3)
    return result


def current_absorption(room: Room) -> dict[str, float]:
    total = {}
    for b in BANDAS_OCTAVA:
        total[b] = sum(s.area * s.material.alpha.get(b, 0) for s in room.superficies)
    return total


def missing_absorption(room: Room, rt60_target: dict[str, float]) -> dict[str, float]:
    req = required_absorption(room.volumen, rt60_target)
    curr = current_absorption(room)
    result = {}
    for b in BANDAS_OCTAVA:
        result[b] = round(max(0, req[b] - curr[b]), 3)
    return result


def suggest_materials(
    room: Room,
    target_uso: str,
    max_suggestions: int = 3,
) -> list[dict]:
    target = get_rt60_target(target_uso)
    if not target:
        return []
    targets = target["valores"]
    missing = missing_absorption(room, targets)

    total_missing = sum(missing.values())
    if total_missing <= 0:
        return [{"mensaje": "La sala ya cumple el RT60 objetivo"}]

    candidates = search_materials(min_alpha_w=0.3)
    candidates.sort(key=lambda m: -(m.alpha_w or 0))

    suggestions = []
    for mat in candidates[:max_suggestions]:
        per_band = {}
        area_needed = 0.0
        for b in BANDAS_OCTAVA:
            if missing[b] <= 0:
                per_band[b] = 0
                continue
            alpha = mat.alpha.get(b, 0.5)
            if alpha > 0:
                a = missing[b] / alpha
                area_needed = max(area_needed, a)
                per_band[b] = round(a, 2)
            else:
                per_band[b] = float('inf')

        if area_needed > 0:
            suggestions.append({
                "material": mat.nombre,
                "area_needed_m2": round(area_needed, 1),
                "alpha_w": mat.alpha_w,
                "iso_class": mat.iso_class,
                "categoria": mat.categoria,
                "per_band": per_band,
            })

    return sorted(suggestions, key=lambda s: s["area_needed_m2"])[:max_suggestions]


AVAILABLE_SURFACES = [
    {"name": "Pared frontal (detrás del listener)", "idx": 0},
    {"name": "Pared trasera", "idx": 1},
    {"name": "Pared lateral izquierda", "idx": 2},
    {"name": "Pared lateral derecha", "idx": 3},
    {"name": "Piso", "idx": 4},
    {"name": "Techo", "idx": 5},
]


def suggest_placement(
    room: Room,
    target_uso: str,
    pressure_map_data: dict | None = None,
) -> list[dict]:
    target = get_rt60_target(target_uso)
    if not target:
        return []
    missing = missing_absorption(room, target["valores"])

    if pressure_map_data and "pressure" in pressure_map_data:
        grid = pressure_map_data["pressure"]
        max_pressure = max(max(row) for row in grid) if grid else 1
        pressure_scores = []
        for s in room.superficies:
            pressure_scores.append(0.5)
        flat = [p / max_pressure if max_pressure > 0 else 0.5 for p in pressure_scores]
    else:
        flat = [0.5] * 6

    placements = []
    for surface, score in zip(AVAILABLE_SURFACES, flat):
        idx = surface["idx"]
        current_area = room.superficies[idx].area
        per_band_abs = {}
        for b in BANDAS_OCTAVA:
            per_band_abs[b] = round(missing[b] * score, 3)
        total_abs = sum(per_band_abs.values())
        if total_abs > 0:
            placements.append({
                "surface": surface["name"],
                "surface_area_m2": current_area,
                "missing_absorption_m2": round(total_abs, 2),
                "priority_score": round(score, 3),
                "coverage_percent": round(min(total_abs / current_area * 100, 100), 1) if current_area > 0 else 0,
            })

    return sorted(placements, key=lambda p: -p["priority_score"])

"""Per-band inverse treatment design with bounded forward verification."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math

from .absorbers import recommended_absorber_area
from .design import get_rt60_target
from .models import BANDAS_OCTAVA, Material, Room
from .presets import MATERIAL_CATALOG_METADATA, MATERIALES_PRESETS, search_materials


SABINE_CONSTANT_S_M = 0.161
TREATMENT_ESTIMATE_LABEL = "engineering_estimate_not_final_construction_design"


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _target_value(rt60_target: Mapping[str, float], band: str) -> float:
    value = _finite(rt60_target.get(band, 0.5), f"rt60_target[{band}]")
    if value < 0.0:
        raise ValueError(f"rt60_target[{band}] must be non-negative")
    return value


def required_absorption(
    volume: float,
    rt60_target: Mapping[str, float],
) -> dict[str, float]:
    """Return the Sabine-equivalent area required independently at each band."""

    room_volume = _finite(volume, "volume")
    if room_volume <= 0.0:
        raise ValueError("volume must be positive")
    result: dict[str, float] = {}
    for band in BANDAS_OCTAVA:
        target = _target_value(rt60_target, band)
        result[band] = (
            math.inf
            if target == 0.0
            else round(SABINE_CONSTANT_S_M * room_volume / target, 3)
        )
    return result


def current_absorption(room: Room) -> dict[str, float]:
    """Return existing equivalent absorption area, separately per octave band."""

    if not isinstance(room, Room):
        raise TypeError("room must be a Room")
    return {
        band: sum(
            surface.area * surface.material.alpha_at(band)
            for surface in room.superficies
        )
        for band in BANDAS_OCTAVA
    }


def missing_absorption(
    room: Room,
    rt60_target: Mapping[str, float],
) -> dict[str, float]:
    required = required_absorption(room.volumen, rt60_target)
    current = current_absorption(room)
    return {
        band: round(max(0.0, required[band] - current[band]), 3)
        for band in BANDAS_OCTAVA
    }


def _resolve_material(material: Material | str) -> Material:
    if isinstance(material, Material):
        return material
    if not isinstance(material, str):
        raise TypeError("treatment material must be a Material or preset name")
    try:
        return MATERIALES_PRESETS[material]
    except KeyError as exc:
        raise KeyError(f"Unknown material preset: {material}") from exc


def treatment_absorption_gain(
    material: Material | str,
    *,
    existing_material: Material | str | None = None,
    installation_mode: str = "added",
) -> dict[str, float]:
    """Return gross (added) or net (replacement) absorption per square metre."""

    if installation_mode not in {"added", "replacement"}:
        raise ValueError("installation_mode must be 'added' or 'replacement'")
    treatment = _resolve_material(material)
    if installation_mode == "added":
        return dict(treatment.alpha)
    if existing_material is None:
        raise ValueError("existing_material is required for replacement mode")
    existing = _resolve_material(existing_material)
    return {
        band: treatment.alpha_at(band) - existing.alpha_at(band)
        for band in BANDAS_OCTAVA
    }


def _predicted_rt60(volume: float, absorption: Mapping[str, float]) -> dict[str, float | None]:
    result: dict[str, float | None] = {}
    for band in BANDAS_OCTAVA:
        area = absorption[band]
        result[band] = (
            None
            if area <= 0.0
            else round(SABINE_CONSTANT_S_M * volume / area, 4)
        )
    return result


def verify_treatment_plan(
    room: Room,
    rt60_target: Mapping[str, float],
    treatments: Sequence[Mapping[str, object]],
) -> dict:
    """Forward-check treatment allocations against their per-band RT target.

    A treatment mapping requires ``material`` and ``area_m2``.  Replacement
    treatments also require ``surface_index``; added treatments may optionally
    carry one for placement reporting.  Replacement patches on each surface
    cannot exceed that surface's physical area.
    """

    if not isinstance(treatments, Sequence) or isinstance(treatments, (str, bytes)):
        raise TypeError("treatments must be a sequence of mappings")
    targets = {band: _target_value(rt60_target, band) for band in BANDAS_OCTAVA}
    if any(value <= 0.0 for value in targets.values()):
        raise ValueError("forward verification requires positive RT60 targets")
    existing_absorption = current_absorption(room)
    predicted_absorption = dict(existing_absorption)
    replacement_area = [0.0] * len(room.superficies)
    normalized_treatments: list[dict] = []

    for treatment_index, treatment_data in enumerate(treatments):
        if not isinstance(treatment_data, Mapping):
            raise TypeError(f"treatments[{treatment_index}] must be a mapping")
        if "material" not in treatment_data or "area_m2" not in treatment_data:
            raise ValueError("each treatment requires material and area_m2")
        material = _resolve_material(treatment_data["material"])
        area = _finite(treatment_data["area_m2"], "treatment area_m2")
        if area < 0.0:
            raise ValueError("treatment area_m2 must be non-negative")
        mode = str(treatment_data.get("installation_mode", "replacement"))
        if mode not in {"added", "replacement"}:
            raise ValueError("installation_mode must be 'added' or 'replacement'")

        raw_surface_index = treatment_data.get("surface_index")
        if raw_surface_index is None:
            surface_index = None
        elif (
            isinstance(raw_surface_index, bool)
            or not isinstance(raw_surface_index, int)
            or not 0 <= raw_surface_index < len(room.superficies)
        ):
            raise ValueError("surface_index is outside the room surface range")
        else:
            surface_index = raw_surface_index
        if mode == "replacement" and surface_index is None:
            raise ValueError("replacement treatment requires surface_index")

        if mode == "replacement":
            replacement_area[surface_index] += area
            surface = room.superficies[surface_index]
            if replacement_area[surface_index] > surface.area + 1e-9:
                raise ValueError(
                    f"replacement area exceeds surface {surface_index} area"
                )
            gain = {
                band: material.alpha_at(band) - surface.material.alpha_at(band)
                for band in BANDAS_OCTAVA
            }
        else:
            gain = dict(material.alpha)

        for band in BANDAS_OCTAVA:
            predicted_absorption[band] += area * gain[band]
        normalized_treatments.append(
            {
                "material": material.nombre,
                "area_m2": round(area, 6),
                "installation_mode": mode,
                "surface_index": surface_index,
                "surface": (
                    None
                    if surface_index is None
                    else room.superficies[surface_index].nombre
                ),
                "absorption_gain_m2_sabins": {
                    band: round(area * gain[band], 6) for band in BANDAS_OCTAVA
                },
            }
        )

    required = required_absorption(room.volumen, targets)
    remaining = {
        band: max(0.0, required[band] - predicted_absorption[band])
        for band in BANDAS_OCTAVA
    }
    predicted_rt60 = _predicted_rt60(room.volumen, predicted_absorption)
    meets_target = {
        band: (
            predicted_rt60[band] is not None
            and predicted_rt60[band] <= targets[band] + 1e-6
        )
        for band in BANDAS_OCTAVA
    }
    return {
        "treatments": normalized_treatments,
        "current_absorption_m2_sabins": {
            band: round(value, 6) for band, value in existing_absorption.items()
        },
        "predicted_absorption_m2_sabins": {
            band: round(value, 6) for band, value in predicted_absorption.items()
        },
        "required_absorption_m2_sabins": required,
        "remaining_missing_absorption_m2_sabins": {
            band: round(value, 6) for band, value in remaining.items()
        },
        "predicted_rt60_s": predicted_rt60,
        "target_rt60_s": targets,
        "meets_target_by_band": meets_target,
        "all_bands_meet": all(meets_target.values()),
        "aggregation_rule": (
            "Each frequency is forward-verified independently; Sabins are not "
            "summed across frequency bands."
        ),
        "estimate_label": TREATMENT_ESTIMATE_LABEL,
    }


AVAILABLE_SURFACES = [
    {"name": "Pared frontal (detrás del listener)", "idx": 0, "key": "front"},
    {"name": "Pared trasera", "idx": 1, "key": "rear"},
    {"name": "Pared lateral izquierda", "idx": 2, "key": "left"},
    {"name": "Pared lateral derecha", "idx": 3, "key": "right"},
    {"name": "Piso", "idx": 4, "key": "floor"},
    {"name": "Techo", "idx": 5, "key": "ceiling"},
]


def _surface_key_index(room: Room, raw_key: object) -> int:
    if isinstance(raw_key, int) and not isinstance(raw_key, bool):
        index = raw_key
    elif isinstance(raw_key, str):
        stripped = raw_key.strip()
        if stripped.isdigit():
            index = int(stripped)
        else:
            lowered = stripped.lower()
            names = {
                surface.nombre.lower(): idx
                for idx, surface in enumerate(room.superficies)
            }
            names.update(
                {
                    descriptor["name"].lower(): descriptor["idx"]
                    for descriptor in AVAILABLE_SURFACES
                }
            )
            names.update(
                {descriptor["key"]: descriptor["idx"] for descriptor in AVAILABLE_SURFACES}
            )
            if lowered not in names:
                raise KeyError(f"Unknown surface key: {raw_key}")
            index = names[lowered]
    else:
        raise TypeError("surface keys must be indices or names")
    if not 0 <= index < len(room.superficies):
        raise KeyError(f"Surface index out of range: {index}")
    return index


def _available_surface_areas(
    room: Room,
    available_area_m2: float | Mapping[object, float] | None,
) -> tuple[list[float], float]:
    physical = [surface.area for surface in room.superficies]
    if available_area_m2 is None:
        return physical, sum(physical)
    if isinstance(available_area_m2, Mapping):
        capacities = [0.0] * len(room.superficies)
        for raw_key, raw_area in available_area_m2.items():
            index = _surface_key_index(room, raw_key)
            area = _finite(raw_area, f"available_area_m2[{raw_key}]")
            if area < 0.0:
                raise ValueError("available surface area must be non-negative")
            capacities[index] = min(area, physical[index])
        return capacities, sum(capacities)
    total = _finite(available_area_m2, "available_area_m2")
    if total < 0.0:
        raise ValueError("available_area_m2 must be non-negative")
    return physical, min(total, sum(physical))


def _normalize_surface_scores(values: Sequence[float]) -> list[float]:
    scores = [_finite(value, "surface pressure score") for value in values]
    if len(scores) != 6 or any(value < 0.0 for value in scores):
        raise ValueError("surface pressure evidence requires six non-negative scores")
    maximum = max(scores)
    if maximum == 0.0:
        return [0.5] * 6
    return [value / maximum for value in scores]


def _surface_pressure_scores(
    room: Room,
    pressure_map_data: Mapping[str, object] | None,
) -> tuple[list[float], str]:
    if pressure_map_data is None:
        return [0.5] * 6, "no pressure evidence; neutral priorities"
    if not isinstance(pressure_map_data, Mapping):
        raise TypeError("pressure_map_data must be a mapping")

    for direct_key in ("surface_scores", "surface_pressure", "surface_evidence"):
        direct = pressure_map_data.get(direct_key)
        if direct is None:
            continue
        if isinstance(direct, Mapping):
            raw_scores = [0.0] * 6
            for raw_surface, raw_score in direct.items():
                raw_scores[_surface_key_index(room, raw_surface)] = raw_score
        elif isinstance(direct, Sequence) and not isinstance(direct, (str, bytes)):
            raw_scores = list(direct)
        else:
            raise TypeError(f"{direct_key} must be a mapping or six-value sequence")
        return _normalize_surface_scores(raw_scores), f"explicit {direct_key}"

    grid_key = next(
        (
            key
            for key in ("energy", "magnitude", "pressure")
            if pressure_map_data.get(key) is not None
        ),
        None,
    )
    if grid_key is None:
        raise ValueError(
            "pressure_map_data requires surface evidence or an energy/magnitude/pressure grid"
        )
    raw_grid = pressure_map_data[grid_key]
    if not isinstance(raw_grid, Sequence) or isinstance(raw_grid, (str, bytes)):
        raise TypeError(f"{grid_key} must be a rectangular grid")
    rows = [list(row) for row in raw_grid]
    if len(rows) < 2 or any(len(row) < 2 for row in rows):
        raise ValueError("pressure grid must be at least 2 by 2")
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        raise ValueError("pressure grid must be rectangular")
    grid: list[list[float]] = []
    for row in rows:
        converted_row = []
        for raw_value in row:
            value = _finite(raw_value, f"{grid_key} grid value")
            converted_row.append(abs(value) if grid_key == "energy" else value * value)
        grid.append(converted_row)

    front = sum(row[0] for row in grid) / len(grid)
    rear = sum(row[-1] for row in grid) / len(grid)
    left = sum(grid[0]) / width
    right = sum(grid[-1]) / width
    horizontal_mean = sum(sum(row) for row in grid) / (len(grid) * width)
    scores = _normalize_surface_scores(
        [front, rear, left, right, 0.35 * horizontal_mean, 0.35 * horizontal_mean]
    )
    return scores, (
        f"{grid_key} boundary evidence: columns map to front/rear, rows to left/right; "
        "floor/ceiling receive low-confidence horizontal-map estimates"
    )


def suggest_placement(
    room: Room,
    target_uso: str,
    pressure_map_data: Mapping[str, object] | None = None,
    *,
    available_area_m2: float | Mapping[object, float] | None = None,
) -> list[dict]:
    target = get_rt60_target(target_uso)
    if not target:
        return []
    missing = missing_absorption(room, target["valores"])
    if not any(value > 0.0 for value in missing.values()):
        return []
    pressure_scores, evidence = _surface_pressure_scores(room, pressure_map_data)
    capacities, _ = _available_surface_areas(room, available_area_m2)
    governing_band = max(BANDAS_OCTAVA, key=lambda band: missing[band])
    governing_missing = missing[governing_band]

    placements: list[dict] = []
    for descriptor, pressure_score, available in zip(
        AVAILABLE_SURFACES, pressure_scores, capacities
    ):
        index = descriptor["idx"]
        surface = room.superficies[index]
        if available <= 0.0:
            continue
        availability_fraction = min(1.0, available / surface.area)
        priority = pressure_score * (0.5 + 0.5 * availability_fraction)
        placements.append(
            {
                "surface": descriptor["name"],
                "room_surface_name": surface.nombre,
                "surface_index": index,
                "surface_area_m2": surface.area,
                "available_area_m2": round(available, 3),
                "missing_absorption_m2": round(governing_missing, 3),
                "missing_absorption_by_band_m2_sabins": dict(missing),
                "governing_band": governing_band,
                "priority_score": round(priority, 6),
                "pressure_evidence_score": round(pressure_score, 6),
                "pressure_evidence": evidence,
                "coverage_percent": (
                    round(min(governing_missing / surface.area * 100.0, 100.0), 1)
                    if surface.area > 0.0
                    else 0.0
                ),
                "aggregation_rule": "governing band; no sum across frequencies",
            }
        )
    return sorted(
        placements,
        key=lambda placement: (-placement["priority_score"], placement["surface_index"]),
    )


def _default_candidates() -> list[Material]:
    return [
        material
        for material in search_materials(min_alpha_w=0.15)
        if MATERIAL_CATALOG_METADATA.get(material.nombre) is None
        or MATERIAL_CATALOG_METADATA[material.nombre].alias_of is None
    ]


def _objective(
    absorption: Mapping[str, float],
    required: Mapping[str, float],
) -> float:
    normalized_deficits = [
        max(0.0, required[band] - absorption[band]) / required[band]
        for band in BANDAS_OCTAVA
    ]
    return max(normalized_deficits) + 0.25 * (
        sum(value * value for value in normalized_deficits) / len(normalized_deficits)
    )


def optimize_treatment(
    room: Room,
    rt60_target: Mapping[str, float],
    *,
    candidate_materials: Sequence[Material | str] | None = None,
    available_area_m2: float | Mapping[object, float] | None = None,
    installation_mode: str = "replacement",
    max_materials: int = 3,
    area_step_m2: float = 0.25,
    pressure_map_data: Mapping[str, object] | None = None,
) -> dict:
    """Greedily minimize the worst normalized band deficit under area bounds.

    The search is deterministic and bounded by available area divided by the
    area step.  It is a practical screening optimizer, not a global optimum.
    """

    if installation_mode not in {"added", "replacement"}:
        raise ValueError("installation_mode must be 'added' or 'replacement'")
    if (
        isinstance(max_materials, bool)
        or not isinstance(max_materials, int)
        or max_materials <= 0
    ):
        raise ValueError("max_materials must be a positive integer")
    area_step = _finite(area_step_m2, "area_step_m2")
    if area_step <= 0.0:
        raise ValueError("area_step_m2 must be positive")
    targets = {band: _target_value(rt60_target, band) for band in BANDAS_OCTAVA}
    if any(value <= 0.0 for value in targets.values()):
        raise ValueError("optimization requires positive RT60 targets")

    if candidate_materials is None:
        candidates = _default_candidates()
    else:
        if not isinstance(candidate_materials, Sequence) or isinstance(
            candidate_materials, (str, bytes)
        ):
            raise TypeError("candidate_materials must be a sequence")
        candidates = [_resolve_material(material) for material in candidate_materials]
    deduplicated: dict[str, Material] = {material.nombre: material for material in candidates}
    candidates = list(deduplicated.values())
    if not candidates:
        raise ValueError("at least one candidate material is required")

    capacities, global_capacity = _available_surface_areas(room, available_area_m2)
    pressure_scores, pressure_evidence = _surface_pressure_scores(room, pressure_map_data)
    required = required_absorption(room.volumen, targets)
    predicted = current_absorption(room)
    initial_missing = {
        band: max(0.0, required[band] - predicted[band]) for band in BANDAS_OCTAVA
    }
    if not any(initial_missing.values()):
        verification = verify_treatment_plan(room, targets, [])
        return {
            "status": "no_treatment_required",
            "installation_mode": installation_mode,
            "allocations": [],
            "available_area_m2": round(global_capacity, 3),
            "used_area_m2": 0.0,
            "optimization_method": "bounded greedy minimax normalized band deficit",
            "pressure_evidence": pressure_evidence,
            "forward_verification": verification,
            "predicted_rt60_s": verification["predicted_rt60_s"],
            "all_bands_meet": True,
            "estimate_label": TREATMENT_ESTIMATE_LABEL,
        }

    gains: dict[tuple[int, str], dict[str, float]] = {}
    for surface_index, surface in enumerate(room.superficies):
        for material in candidates:
            gains[(surface_index, material.nombre)] = {
                band: (
                    material.alpha_at(band)
                    if installation_mode == "added"
                    else material.alpha_at(band) - surface.material.alpha_at(band)
                )
                for band in BANDAS_OCTAVA
            }

    allocated_by_surface = [0.0] * len(room.superficies)
    allocation_areas: dict[tuple[int, str], float] = {}
    selected_materials: set[str] = set()
    used_total = 0.0
    current_objective = _objective(predicted, required)
    max_iterations = math.ceil(global_capacity / area_step) + len(room.superficies) + 1

    for _ in range(max_iterations):
        if current_objective <= 1e-12 or used_total >= global_capacity - 1e-12:
            break
        best: tuple[tuple[float, float, float, int, str], int, Material, float, dict[str, float], float] | None = None
        for surface_index, capacity in enumerate(capacities):
            surface_remaining = capacity - allocated_by_surface[surface_index]
            if surface_remaining <= 1e-12:
                continue
            delta = min(area_step, surface_remaining, global_capacity - used_total)
            if delta <= 1e-12:
                continue
            for material in candidates:
                if (
                    material.nombre not in selected_materials
                    and len(selected_materials) >= max_materials
                ):
                    continue
                gain = gains[(surface_index, material.nombre)]
                trial = {
                    band: predicted[band] + delta * gain[band]
                    for band in BANDAS_OCTAVA
                }
                trial_objective = _objective(trial, required)
                improvement_per_area = (current_objective - trial_objective) / delta
                tie_break = (
                    improvement_per_area,
                    pressure_scores[surface_index],
                    material.alpha_w or 0.0,
                    -surface_index,
                    material.nombre,
                )
                candidate = (
                    tie_break,
                    surface_index,
                    material,
                    delta,
                    trial,
                    trial_objective,
                )
                if best is None or candidate[0] > best[0]:
                    best = candidate
        if best is None or best[0][0] <= 1e-12:
            break
        _, surface_index, material, delta, predicted, current_objective = best
        key = (surface_index, material.nombre)
        allocation_areas[key] = allocation_areas.get(key, 0.0) + delta
        allocated_by_surface[surface_index] += delta
        selected_materials.add(material.nombre)
        used_total += delta

    treatment_inputs: list[dict] = []
    for (surface_index, material_name), area in sorted(allocation_areas.items()):
        treatment_inputs.append(
            {
                "material": MATERIALES_PRESETS.get(
                    material_name, deduplicated[material_name]
                ),
                "area_m2": area,
                "surface_index": surface_index,
                "installation_mode": installation_mode,
            }
        )
    verification = verify_treatment_plan(room, targets, treatment_inputs)
    allocations = verification["treatments"]
    status = "feasible" if verification["all_bands_meet"] else "area_limited"
    if not allocations:
        status = "no_improving_allocation"
    return {
        "status": status,
        "installation_mode": installation_mode,
        "allocations": allocations,
        "selected_materials": sorted(selected_materials),
        "available_area_m2": round(global_capacity, 3),
        "available_area_by_surface_m2": {
            str(index): round(area, 3) for index, area in enumerate(capacities)
        },
        "used_area_m2": round(used_total, 6),
        "area_step_m2": area_step,
        "optimization_method": (
            "bounded greedy minimax plus mean-square normalized per-band deficit; "
            "no cross-frequency Sabin sum"
        ),
        "pressure_evidence": pressure_evidence,
        "forward_verification": verification,
        "predicted_rt60_s": verification["predicted_rt60_s"],
        "all_bands_meet": verification["all_bands_meet"],
        "estimate_label": TREATMENT_ESTIMATE_LABEL,
    }


def design_treatment(
    room: Room,
    target_uso: str,
    **optimization_options,
) -> dict:
    """Usage-name convenience wrapper for :func:`optimize_treatment`."""

    target = get_rt60_target(target_uso)
    if target is None:
        raise ValueError(f"Unknown RT60 target use: {target_uso}")
    result = optimize_treatment(room, target["valores"], **optimization_options)
    result["target_uso"] = target_uso
    result["target_label"] = target["label"]
    return result


def suggest_materials(
    room: Room,
    target_uso: str,
    max_suggestions: int = 3,
    *,
    installation_mode: str = "replacement",
    available_area_m2: float | Mapping[object, float] | None = None,
) -> list[dict]:
    """Compatibility suggestions with corrected gross/net area semantics."""

    target = get_rt60_target(target_uso)
    if not target:
        return []
    missing = missing_absorption(room, target["valores"])
    if not any(value > 0.0 for value in missing.values()):
        return [{"mensaje": "La sala ya cumple el RT60 objetivo"}]
    if (
        isinstance(max_suggestions, bool)
        or not isinstance(max_suggestions, int)
        or max_suggestions <= 0
    ):
        return []

    capacities, total_available = _available_surface_areas(room, available_area_m2)
    del capacities
    weighted_existing = {
        band: current_absorption(room)[band] / room.superficie_total
        for band in BANDAS_OCTAVA
    }
    candidates = _default_candidates()
    suggestions: list[dict] = []
    for material in candidates:
        area_result = recommended_absorber_area(
            material.alpha,
            missing,
            existing_surface_alpha=weighted_existing,
            installation_mode=installation_mode,
            available_area_m2=total_available,
        )
        area_needed = area_result["recommended_area_m2"]
        if area_needed is None or area_needed <= 0.0:
            continue
        predicted_absorption = {
            band: current_absorption(room)[band]
            + area_needed
            * area_result["effective_absorption_coefficients"][band]
            for band in BANDAS_OCTAVA
        }
        suggestions.append(
            {
                "material": material.nombre,
                "area_needed_m2": round(area_needed, 1),
                "alpha_w": material.alpha_w,
                "iso_class": material.iso_class,
                "categoria": material.categoria,
                "per_band": {
                    band: float(area_result["per_band_area_m2"][band])
                    for band in BANDAS_OCTAVA
                },
                "installation_mode": installation_mode,
                "available_area_m2": round(total_available, 3),
                "feasible": area_result["feasible"],
                "governing_bands": area_result["governing_bands"],
                "predicted_rt60_s": _predicted_rt60(
                    room.volumen, predicted_absorption
                ),
                "estimate_label": TREATMENT_ESTIMATE_LABEL,
            }
        )
    suggestions.sort(
        key=lambda suggestion: (
            not suggestion["feasible"],
            suggestion["area_needed_m2"],
            suggestion["material"],
        )
    )
    return suggestions[:max_suggestions]

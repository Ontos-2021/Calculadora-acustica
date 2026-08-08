import math
from dataclasses import dataclass, field
from typing import Optional
from .models import Material, BANDAS_OCTAVA


def classify_iso11654(alphas: dict[str, float]) -> tuple[float, str]:
    vals = [alphas.get(b, 0) for b in ["250", "500", "1000", "2000"]]
    alpha_w = min(round(sum(vals) / len(vals) / 0.05) * 0.05, 1.0)
    if alpha_w >= 0.90:
        iso_class = "A"
    elif alpha_w >= 0.80:
        iso_class = "B"
    elif alpha_w >= 0.60:
        iso_class = "C"
    elif alpha_w >= 0.30:
        iso_class = "D"
    elif alpha_w >= 0.15:
        iso_class = "E"
    else:
        iso_class = "No clasificado"
    return alpha_w, iso_class


MATERIALES_PRESETS: dict[str, Material] = {}

_CAT: dict[str, list[dict]] = {
    "Mampostería": [
        {"nombre": "Concreto pulido", "alphas": {"125": 0.01, "250": 0.01, "500": 0.02, "1000": 0.02, "2000": 0.03, "4000": 0.03}},
        {"nombre": "Concreto sin pintar", "alphas": {"125": 0.01, "250": 0.02, "500": 0.04, "1000": 0.06, "2000": 0.08, "4000": 0.10}},
        {"nombre": "Ladrillo visto", "alphas": {"125": 0.03, "250": 0.03, "500": 0.04, "1000": 0.05, "2000": 0.06, "4000": 0.07}},
        {"nombre": "Ladrillo enlucido", "alphas": {"125": 0.02, "250": 0.02, "500": 0.03, "1000": 0.04, "2000": 0.05, "4000": 0.05}},
        {"nombre": "Bloque de hormigón hueco", "alphas": {"125": 0.05, "250": 0.04, "500": 0.03, "1000": 0.04, "2000": 0.05, "4000": 0.05}},
        {"nombre": "Piedra natural", "alphas": {"125": 0.01, "250": 0.01, "500": 0.02, "1000": 0.02, "2000": 0.03, "4000": 0.03}},
    ],
    "Madera": [
        {"nombre": "Madera contrachapada (10mm)", "alphas": {"125": 0.05, "250": 0.05, "500": 0.07, "1000": 0.06, "2000": 0.06, "4000": 0.07}},
        {"nombre": "Madera maciza (20mm)", "alphas": {"125": 0.05, "250": 0.04, "500": 0.04, "1000": 0.05, "2000": 0.05, "4000": 0.06}},
        {"nombre": "Parquet sobre hormigón", "alphas": {"125": 0.04, "250": 0.04, "500": 0.05, "1000": 0.05, "2000": 0.06, "4000": 0.06}},
        {"nombre": "Panel de madera perforado", "alphas": {"125": 0.15, "250": 0.25, "500": 0.40, "1000": 0.30, "2000": 0.20, "4000": 0.15}},
        {"nombre": "MDF (12mm)", "alphas": {"125": 0.05, "250": 0.05, "500": 0.06, "1000": 0.06, "2000": 0.06, "4000": 0.07}},
    ],
    "Pisos": [
        {"nombre": "Alfombra gruesa sobre espuma", "alphas": {"125": 0.08, "250": 0.24, "500": 0.57, "1000": 0.69, "2000": 0.71, "4000": 0.73}},
        {"nombre": "Alfombra sobre moqueta", "alphas": {"125": 0.05, "250": 0.10, "500": 0.25, "1000": 0.40, "2000": 0.50, "4000": 0.55}},
        {"nombre": "Alfombra fina sobre hormigón", "alphas": {"125": 0.02, "250": 0.06, "500": 0.14, "1000": 0.37, "2000": 0.48, "4000": 0.52}},
        {"nombre": "Linóleo sobre hormigón", "alphas": {"125": 0.02, "250": 0.03, "500": 0.03, "1000": 0.04, "2000": 0.04, "4000": 0.05}},
        {"nombre": "Baldosa vinílica", "alphas": {"125": 0.02, "250": 0.02, "500": 0.03, "1000": 0.03, "2000": 0.04, "4000": 0.04}},
        {"nombre": "Suelo de goma", "alphas": {"125": 0.04, "250": 0.04, "500": 0.08, "1000": 0.12, "2000": 0.10, "4000": 0.10}},
    ],
    "Techos": [
        {"nombre": "Escayola lisa", "alphas": {"125": 0.04, "250": 0.04, "500": 0.05, "1000": 0.06, "2000": 0.08, "4000": 0.08}},
        {"nombre": "Escayola acústica", "alphas": {"125": 0.10, "250": 0.15, "500": 0.30, "1000": 0.40, "2000": 0.35, "4000": 0.30}},
        {"nombre": "Falso techo mineral (suspendido)", "alphas": {"125": 0.15, "250": 0.40, "500": 0.70, "1000": 0.80, "2000": 0.75, "4000": 0.65}},
        {"nombre": "Panel metálico perforado", "alphas": {"125": 0.10, "250": 0.30, "500": 0.60, "1000": 0.65, "2000": 0.55, "4000": 0.45}},
    ],
    "Vidrio": [
        {"nombre": "Vidrio simple (3-6mm)", "alphas": {"125": 0.03, "250": 0.03, "500": 0.05, "1000": 0.08, "2000": 0.10, "4000": 0.10}},
        {"nombre": "Vidrio doble (4-12-4)", "alphas": {"125": 0.02, "250": 0.02, "500": 0.04, "1000": 0.05, "2000": 0.06, "4000": 0.06}},
        {"nombre": "Vidrio laminado", "alphas": {"125": 0.03, "250": 0.03, "500": 0.05, "1000": 0.07, "2000": 0.08, "4000": 0.08}},
        {"nombre": "Cristal blindado", "alphas": {"125": 0.02, "250": 0.02, "500": 0.03, "1000": 0.04, "2000": 0.05, "4000": 0.05}},
    ],
    "Telas y cortinas": [
        {"nombre": "Cortina ligera (plegada 50%)", "alphas": {"125": 0.05, "250": 0.12, "500": 0.20, "1000": 0.35, "2000": 0.45, "4000": 0.50}},
        {"nombre": "Cortina pesada (terciopelo)", "alphas": {"125": 0.10, "250": 0.30, "500": 0.50, "1000": 0.65, "2000": 0.70, "4000": 0.70}},
        {"nombre": "Cortina media (plegada 100%)", "alphas": {"125": 0.07, "250": 0.20, "500": 0.35, "1000": 0.50, "2000": 0.55, "4000": 0.55}},
        {"nombre": "Moqueta de lana (6mm)", "alphas": {"125": 0.08, "250": 0.10, "500": 0.25, "1000": 0.40, "2000": 0.45, "4000": 0.50}},
    ],
    "Paneles acústicos": [
        {"nombre": "Panel fibra de vidrio (50mm)", "alphas": {"125": 0.20, "250": 0.60, "500": 0.85, "1000": 0.90, "2000": 0.85, "4000": 0.80}},
        {"nombre": "Panel fibra de vidrio (25mm)", "alphas": {"125": 0.10, "250": 0.35, "500": 0.70, "1000": 0.85, "2000": 0.80, "4000": 0.75}},
        {"nombre": "Lana mineral (50mm)", "alphas": {"125": 0.25, "250": 0.55, "500": 0.75, "1000": 0.85, "2000": 0.80, "4000": 0.75}},
        {"nombre": "Lana mineral (100mm)", "alphas": {"125": 0.35, "250": 0.75, "500": 0.90, "1000": 0.95, "2000": 0.90, "4000": 0.85}},
        {"nombre": "Panel microperforado", "alphas": {"125": 0.15, "250": 0.40, "500": 0.70, "1000": 0.65, "2000": 0.50, "4000": 0.40}},
        {"nombre": "Panel de fibra de madera", "alphas": {"125": 0.20, "250": 0.50, "500": 0.75, "1000": 0.80, "2000": 0.75, "4000": 0.70}},
    ],
    "Espumas": [
        {"nombre": "Espuma de poliuretano (50mm)", "alphas": {"125": 0.15, "250": 0.35, "500": 0.65, "1000": 0.80, "2000": 0.80, "4000": 0.75}},
        {"nombre": "Espuma de melamina (50mm)", "alphas": {"125": 0.15, "250": 0.30, "500": 0.60, "1000": 0.80, "2000": 0.85, "4000": 0.80}},
        {"nombre": "Espuma de poliuretano (25mm)", "alphas": {"125": 0.10, "250": 0.20, "500": 0.45, "1000": 0.60, "2000": 0.65, "4000": 0.60}},
    ],
}


_OLD_NAMES = {
    "Concreto": "Concreto sin pintar",
    "Madera": "Madera contrachapada (10mm)",
    "Yeso": "Escayola lisa",
    "Vidrio": "Vidrio simple (3-6mm)",
    "Alfombra gruesa": "Alfombra gruesa sobre espuma",
    "Cortina pesada": "Cortina pesada (terciopelo)",
    "Panel acústico": "Panel fibra de vidrio (50mm)",
    "Espuma acústica": "Espuma de poliuretano (50mm)",
}

for _cat_name, _entries in _CAT.items():
    for _e in _entries:
        name = _e["nombre"]
        MAT = Material(nombre=name, alphas=_e["alphas"])
        MAT.categoria = _cat_name
        w, cls = classify_iso11654(_e["alphas"])
        MAT.alpha_w = w
        MAT.iso_class = cls
        MATERIALES_PRESETS[name] = MAT

for _old, _new in _OLD_NAMES.items():
    if _new in MATERIALES_PRESETS:
        src = MATERIALES_PRESETS[_new]
        old_mat = Material(nombre=_old, alphas=src.alphas)
        old_mat.categoria = src.categoria
        old_mat.alpha_w = src.alpha_w
        old_mat.iso_class = src.iso_class
        MATERIALES_PRESETS[_old] = old_mat


CATEGORIAS: dict[str, list[str]] = {}
for name, mat in MATERIALES_PRESETS.items():
    CATEGORIAS.setdefault(mat.categoria, []).append(name)


def search_materials(
    query: str = "",
    categoria: str = "",
    min_alpha_w: float = 0.0,
    max_alpha_w: float = 1.0,
    iso_class: str = "",
) -> list[Material]:
    results = []
    for mat in MATERIALES_PRESETS.values():
        if categoria and mat.categoria != categoria:
            continue
        if mat.alpha_w is not None and (mat.alpha_w < min_alpha_w or mat.alpha_w > max_alpha_w):
            continue
        if iso_class and mat.iso_class != iso_class:
            continue
        if query and query.lower() not in mat.nombre.lower():
            continue
        results.append(mat)
    return results


def calculate_air_absorption(
    frequency_hz: float,
    humidity_percent: float = 50.0,
    temp_celsius: float = 20.0,
) -> float:
    Tk = temp_celsius + 273.15
    pr = 101325.0
    hr = humidity_percent / 100.0
    psv = 4.6151 * hr * 10 ** (8.07131 - 1730.63 / (233.426 + temp_celsius))
    h = hr * (psv / pr) / (psv / pr)
    fr_o = pr / psv * (24 + 4.04e4 * h * (0.02 + h) / (0.391 + h))
    fr_N = pr / psv * (9 + 280 * h * math.exp(-4.17 * ((psv / pr) ** (-1 / 3) - 0.2)))
    m = frequency_hz ** 2 * (
        1.84e-11 * (pr / Tk) ** (-1)
        + (Tk / 293) ** (-2.5)
        * (
            0.01278 * math.exp(-fr_o / frequency_hz) / (fr_o + frequency_hz ** 2 / fr_o)
            + 0.1068 * math.exp(-fr_N / frequency_hz) / (fr_N + frequency_hz ** 2 / fr_N)
        )
    )
    return m


AIR_ABSORPTION_DEFAULT = {
    b: calculate_air_absorption(float(b), 50.0, 20.0) for b in BANDAS_OCTAVA
}


@dataclass
class AudienceConfig:
    num_people: int = 0
    seated: bool = True
    upholstered: bool = True
    occupied: float = 0.85


AUDIENCE_ABSORPTION_PER_PERSON: dict[str, float] = {
    "125": 0.20, "250": 0.30, "500": 0.40, "1000": 0.45, "2000": 0.50, "4000": 0.45,
}
AUDIENCE_ABSORPTION_STANDING: dict[str, float] = {
    "125": 0.10, "250": 0.20, "500": 0.30, "1000": 0.35, "2000": 0.40, "4000": 0.35,
}
EMPTY_SEAT_ABSORPTION: dict[str, float] = {
    "125": 0.10, "250": 0.15, "500": 0.20, "1000": 0.25, "2000": 0.25, "4000": 0.25,
}


def calculate_audience_absorption(config: AudienceConfig) -> dict[str, float]:
    per_person = AUDIENCE_ABSORPTION_STANDING if not config.seated else AUDIENCE_ABSORPTION_PER_PERSON
    total = {}
    for b in BANDAS_OCTAVA:
        a = per_person[b] * config.num_people * config.occupied
        a += EMPTY_SEAT_ABSORPTION[b] * config.num_people * (1 - config.occupied)
        total[b] = round(a, 3)
    return total

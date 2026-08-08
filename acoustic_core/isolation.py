import math
from .models import BANDAS_OCTAVA

C = 343.0


def mass_law_tl(mass_per_area_kgm2: float, frequency_hz: float) -> float:
    if mass_per_area_kgm2 <= 0 or frequency_hz <= 0:
        return 0
    return round(max(0, 20 * math.log10(mass_per_area_kgm2 * frequency_hz) - 47), 1)


MATERIAL_C_L: dict[str, float] = {
    "concreto": 3500,
    "yeso": 1700,
    "madera": 3200,
    "acero": 5200,
    "vidrio": 5200,
    "ladrillo": 3000,
    "aluminio": 5100,
    "fibrocemento": 2500,
}


def critical_frequency(thickness_m: float, c_l_material: float = 3500.0) -> float:
    if thickness_m <= 0:
        return float('inf')
    return round(C ** 2 / (1.8 * c_l_material * thickness_m), 1)


def coincidence_notch(frequency_hz: float, fc: float, depth_db: float = 10) -> float:
    if fc <= 0 or fc == float('inf'):
        return 0
    ratio = frequency_hz / fc
    return round(depth_db * math.exp(-((math.log2(ratio) ** 2) / 0.5)), 1)


def single_panel_tl(
    mass_per_area_kgm2: float,
    thickness_m: float,
    material_type: str = "concreto",
) -> dict[str, float]:
    c_l = MATERIAL_C_L.get(material_type, 3500)
    fc = critical_frequency(thickness_m, c_l)
    result = {}
    for b in BANDAS_OCTAVA:
        f = float(b)
        tl = mass_law_tl(mass_per_area_kgm2, f)
        notch = coincidence_notch(f, fc)
        result[b] = round(max(0, tl - notch), 1)
    return result


def msr_resonance(m1: float, m2: float, gap_m: float) -> float:
    if m1 <= 0 or m2 <= 0 or gap_m <= 0:
        return 0
    return round(60 * math.sqrt((m1 + m2) / (m1 * m2 * gap_m)), 1)


def double_panel_tl(
    m1: float,
    m2: float,
    gap_m: float,
    stud_connection: bool = True,
) -> dict[str, float]:
    f0 = msr_resonance(m1, m2, gap_m)
    connector_penalty = 5 if stud_connection else 0
    result = {}
    for b in BANDAS_OCTAVA:
        f = float(b)
        tl1 = mass_law_tl(m1, f)
        tl2 = mass_law_tl(m2, f)
        tl_mass = tl1 + tl2
        if f < f0 / 2:
            tl = tl1 + tl2 - 6
        elif f < f0 * math.sqrt(2):
            slope = (tl1 + tl2) / (f0 * math.sqrt(2) - f0 / 2)
            tl = tl1 + tl2 - 6 + slope * (f - f0 / 2)
        else:
            tl = tl1 + tl2 + 6
        tl = max(tl - connector_penalty, 0)
        result[b] = round(tl, 1)
    return result


STC_REFERENCE: list[tuple[int, float]] = [
    (125, 30), (160, 33), (200, 36), (250, 39),
    (315, 42), (400, 45), (500, 48), (630, 51),
    (800, 54), (1000, 57), (1250, 60), (1600, 63),
    (2000, 66), (2500, 69), (3150, 72), (4000, 75),
]


def calculate_stc(tl_curve: dict[str, float]) -> dict:
    freqs = sorted((int(k), v) for k, v in tl_curve.items())
    ref_map = dict(STC_REFERENCE)

    for shift in range(100, -1, -1):
        deficiencies = 0
        for f, tl in freqs:
            ref = ref_map.get(f, 0) + shift
            if tl < ref:
                deficiencies += ref - tl
        if deficiencies <= 32:
            stc = shift - 1 if shift < 100 else 100
            return {"stc": stc, "shift": stc, "deficiencies": round(deficiencies, 1)}
    return {"stc": 0, "shift": 0, "deficiencies": 100}


def calculate_rw(tl_curve: dict[str, float]) -> dict:
    iso_ref: list[tuple[int, float]] = [
        (100, 33), (125, 36), (160, 39), (200, 42),
        (250, 45), (315, 48), (400, 51), (500, 54),
        (630, 57), (800, 60), (1000, 63), (1250, 66),
        (1600, 69), (2000, 72), (2500, 75), (3150, 78),
    ]
    freqs = sorted((int(k), v) for k, v in tl_curve.items())
    ref_map = dict(iso_ref)
    for shift in range(100, -1, -1):
        deficiencies = 0
        for f, tl in freqs:
            ref = ref_map.get(f, 0) + shift
            if tl < ref:
                deficiencies += ref - tl
        if deficiencies <= 32:
            rw = shift - 1 if shift < 100 else 100
            return {"rw": rw, "shift": rw, "deficiencies": round(deficiencies, 1)}
    return {"rw": 0, "shift": 0, "deficiencies": 100}


NC_CURVES: dict[int, list[float]] = {
    nc: [
        max(0, nc + round(10 * math.log10(
            (f / 1000) ** 3 / (1 + (f / 1000) ** 2) / (1 + (f / 4000) ** 2)
        ), 0) + 22) if f >= 63 else nc + 10
        for f in [63, 125, 250, 500, 1000, 2000, 4000, 8000]
    ]
    for nc in range(0, 71, 5)
}

NC_FREQS = [63, 125, 250, 500, 1000, 2000, 4000, 8000]


def evaluate_nc(spl_curve: dict[str, float]) -> dict:
    def nc_value_for_band(f_hz: int, spl: float) -> int:
        best_nc = 0
        for nc_val, curve in NC_CURVES.items():
            idx = NC_FREQS.index(f_hz) if f_hz in NC_FREQS else -1
            if idx >= 0 and spl > curve[idx]:
                best_nc = nc_val
        return best_nc

    nc_by_band = {}
    max_nc = 0
    for b in BANDAS_OCTAVA:
        f = int(b)
        spl = spl_curve.get(b, 0)
        nc_val = nc_value_for_band(f, spl)
        nc_by_band[b] = nc_val
        if nc_val > max_nc:
            max_nc = nc_val
    return {"nc": max_nc, "nc_by_band": nc_by_band}


NC_TARGETS: dict[str, dict] = {
    "estudio_grabacion": {"label": "Estudio de grabación", "nc": 15, "nc_max": 20},
    "sala_conciertos": {"label": "Sala de conciertos", "nc": 15, "nc_max": 20},
    "teatro": {"label": "Teatro", "nc": 20, "nc_max": 25},
    "oficina_ejecutiva": {"label": "Oficina ejecutiva", "nc": 25, "nc_max": 30},
    "aula": {"label": "Aula", "nc": 25, "nc_max": 30},
    "restaurante": {"label": "Restaurante", "nc": 35, "nc_max": 40},
}


def get_nc_target(uso: str) -> dict | None:
    return NC_TARGETS.get(uso)

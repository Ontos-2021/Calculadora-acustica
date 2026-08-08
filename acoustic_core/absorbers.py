import math
import cmath
from .models import BANDAS_OCTAVA

C = 343.0
RHO = 1.2


def _frequency_value(banda: str) -> float:
    return float(banda)


def porous_absorption(
    thickness_m: float,
    flow_resistivity: float,
    density_kgm3: float = 100.0,
) -> dict[str, float]:
    result = {}
    for b in BANDAS_OCTAVA:
        f = _frequency_value(b)
        if thickness_m <= 0 or flow_resistivity <= 0:
            result[b] = 0.0
            continue
        E = RHO * f / flow_resistivity
        if E <= 0:
            result[b] = 0.0
            continue
        E_pow = E ** -0.754
        Zc = C * RHO * (1 + 0.0571 * E_pow - 1j * 0.087 * E ** -0.732)
        k = (2 * math.pi * f / C) * (1 + 0.0978 * E ** -0.700 - 1j * 0.189 * E ** -0.595)
        cot_kd = 1 / cmath.tan(k * thickness_m)
        Zs = -1j * Zc * cot_kd
        R = (Zs - C * RHO) / (Zs + C * RHO)
        alpha = 1 - abs(R) ** 2
        result[b] = round(min(max(alpha, 0), 1), 4)
    return result


def helmholtz_resonator(
    neck_area_m2: float,
    cavity_volume_m3: float,
    neck_length_m: float,
    neck_radius_m: float = 0.02,
) -> dict:
    if neck_area_m2 <= 0 or cavity_volume_m3 <= 0:
        return {"f0": 0, "alpha": {b: 0.0 for b in BANDAS_OCTAVA}}
    end_correction = 0.85 * neck_radius_m
    L_eff = neck_length_m + end_correction
    f0 = (C / (2 * math.pi)) * math.sqrt(neck_area_m2 / (cavity_volume_m3 * L_eff))
    Q = 2 * math.pi * f0 * cavity_volume_m3 / (C * neck_area_m2)
    alpha = {}
    for b in BANDAS_OCTAVA:
        f = _frequency_value(b)
        df = f / f0 - f0 / f
        abs_coeff = 1 / (1 + (Q * df) ** 2)
        alpha[b] = round(abs_coeff, 4)
    return {"f0": round(f0, 1), "alpha": alpha, "Q": round(Q, 1)}


def membrane_absorber(
    mass_per_area_kgm2: float,
    air_gap_m: float,
) -> dict:
    if mass_per_area_kgm2 <= 0 or air_gap_m <= 0:
        return {"f0": 0, "alpha": {b: 0.0 for b in BANDAS_OCTAVA}}
    f0 = 60.0 / math.sqrt(mass_per_area_kgm2 * air_gap_m)
    Q = 10.0
    alpha = {}
    for b in BANDAS_OCTAVA:
        f = _frequency_value(b)
        df = f / f0 - f0 / f
        abs_coeff = 1 / (1 + (Q * df) ** 2)
        alpha[b] = round(abs_coeff, 4)
    return {"f0": round(f0, 1), "alpha": alpha, "Q": Q}

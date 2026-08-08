import math
import cmath
from .models import BANDAS_OCTAVA

C = 343.0
RHO = 1.2


def axial_modes_finite_impedance(
    L_m: float,
    Z_wall_real: float = 10000,
    Z_wall_imag: float = 0,
    max_modes: int = 5,
) -> list[dict]:
    Z_wall = complex(Z_wall_real, Z_wall_imag)
    rhs = -1j * RHO * C / Z_wall
    modes = []
    for n in range(1, max_modes + 1):
        k_rigid = n * math.pi / L_m
        f_rigid = k_rigid * C / (2 * math.pi)
        kz = k_rigid
        for _ in range(100):
            t = cmath.tan(kz * L_m)
            fk = t - rhs
            dt = L_m / (cmath.cos(kz * L_m) ** 2)
            if abs(dt) < 1e-15:
                break
            kz_new = kz - fk / dt
            if abs(kz_new - kz) < 1e-10:
                break
            kz = kz_new
        f_complex = kz * C / (2 * math.pi)
        rt60_est = 2.2 / abs(f_complex.imag) if abs(f_complex.imag) > 1e-10 else 0
        modes.append({
            "n": n,
            "frequency_hz": round(f_complex.real, 2),
            "rigid_frequency_hz": round(f_rigid, 2),
            "damping_neper_s": round(f_complex.imag, 4),
            "rt60_estimate_s": round(rt60_est, 3),
            "shift_hz": round(f_complex.real - f_rigid, 3),
        })
    return modes


def room_modes_finite_impedance(
    L: float,
    W: float,
    H: float,
    Z_wall: float = 10000,
    max_order: int = 3,
) -> list[dict]:
    modes = []
    for nx in range(max_order + 1):
        for ny in range(max_order + 1):
            for nz in range(max_order + 1):
                if nx == 0 and ny == 0 and nz == 0:
                    continue
                kx = nx * math.pi / L
                ky = ny * math.pi / W
                kz = nz * math.pi / H
                k_sq = kx ** 2 + ky ** 2 + kz ** 2
                f_rigid = C / (2 * math.pi) * math.sqrt(k_sq)
                Z = complex(Z_wall, 0)
                damp = 0
                if Z.real > 0:
                    beta = RHO * C / Z.real
                    if nx > 0:
                        damp += beta * (kx ** 2 / k_sq) * C / (2 * L)
                    if ny > 0:
                        damp += beta * (ky ** 2 / k_sq) * C / (2 * W)
                    if nz > 0:
                        damp += beta * (kz ** 2 / k_sq) * C / (2 * H)
                rt60 = 2.2 / damp if damp > 0 else 0
                modes.append({
                    "indices": [nx, ny, nz],
                    "rigid_frequency_hz": round(f_rigid, 2),
                    "damping": round(damp, 4),
                    "rt60_estimate_s": round(rt60, 3),
                })
    return sorted(modes, key=lambda m: m["rigid_frequency_hz"])

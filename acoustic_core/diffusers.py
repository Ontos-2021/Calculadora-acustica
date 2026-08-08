import math
from .models import BANDAS_OCTAVA

C = 343.0


def _primes_up_to(n: int) -> list[int]:
    sieve = [True] * (n + 1)
    sieve[0] = sieve[1] = False
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            for j in range(i * i, n + 1, i):
                sieve[j] = False
    return [i for i, v in enumerate(sieve) if v]


PRIMES = _primes_up_to(200)


def _nearest_prime(n: int) -> int:
    for p in PRIMES:
        if p >= n:
            return p
    return PRIMES[-1]


def qrd_well_depths(
    design_freq_hz: float,
    prime_n: int = 17,
    well_width_m: float = 0.05,
) -> dict:
    if design_freq_hz <= 0 or prime_n < 3:
        return {"error": "Parámetros inválidos"}
    prime_n = _nearest_prime(prime_n)
    lambda_0 = C / design_freq_hz
    max_depth = lambda_0 / 2
    depths = []
    for n in range(prime_n):
        d = max_depth * ((n * n) % prime_n) / prime_n
        depths.append(round(d, 4))
    total_width = prime_n * well_width_m
    min_freq = C / (2 * max_depth)
    return {
        "type": "QRD",
        "prime_n": prime_n,
        "design_freq_hz": design_freq_hz,
        "well_width_m": well_width_m,
        "total_width_m": round(total_width, 3),
        "max_depth_m": round(max_depth, 4),
        "min_effective_freq_hz": round(min_freq, 1),
        "well_depths_m": depths,
        "sequence": [(n * n) % prime_n for n in range(prime_n)],
    }


def skyline_well_depths(
    design_freq_hz: float,
    grid_n: int = 7,
    well_size_m: float = 0.05,
) -> dict:
    if design_freq_hz <= 0 or grid_n < 2:
        return {"error": "Parámetros inválidos"}
    lambda_0 = C / design_freq_hz
    max_depth = lambda_0 / 2
    depths_2d = []
    for i in range(grid_n):
        row = []
        for j in range(grid_n):
            val = ((i + 1) * (j + 1)) % (grid_n + 2) or 1
            d = max_depth * val / (grid_n + 2)
            row.append(round(d, 4))
        depths_2d.append(row)
    return {
        "type": "Skyline",
        "grid_n": grid_n,
        "design_freq_hz": design_freq_hz,
        "well_size_m": well_size_m,
        "total_width_m": round(grid_n * well_size_m, 3),
        "max_depth_m": round(max_depth, 4),
        "min_effective_freq_hz": round(C / (2 * max_depth), 1),
        "well_depths_m": depths_2d,
    }


def estimate_diffusion_coefficient(
    design_freq_hz: float,
    max_depth_m: float,
) -> dict[str, float]:
    result = {}
    for b in BANDAS_OCTAVA:
        f = float(b)
        if f <= 0:
            result[b] = 0
            continue
        ratio = f / design_freq_hz
        if ratio < 0.25:
            d_coeff = 0.05
        elif ratio < 0.5:
            d_coeff = 0.1 + 0.3 * (ratio - 0.25) / 0.25
        elif ratio < 1.0:
            d_coeff = 0.4 + 0.4 * (ratio - 0.5) / 0.5
        elif ratio < 2.0:
            d_coeff = 0.8 + 0.15 * (ratio - 1.0) / 1.0
        else:
            d_coeff = 0.95 - 0.1 * min(ratio - 2.0, 1.0)
        result[b] = round(max(0, min(1, d_coeff)), 3)
    return result

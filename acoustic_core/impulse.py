import math
from typing import Optional
from .models import Room, BANDAS_OCTAVA


def _image_position(
    s: float, L: float, k: int,
) -> tuple[float, int, int]:
    """Retorna (posición imagen, count_reflection_positiva, count_reflection_negativa)"""
    sign = 1 if k % 2 == 0 else -1
    shift = -k // 2 if k % 2 == 0 else (k + 1) // 2
    img = sign * s + 2 * shift * L

    if k > 0:
        cnt_pos = (k + 1) // 2
        cnt_neg = k // 2
    elif k < 0:
        cnt_pos = (-k) // 2
        cnt_neg = (-k + 1) // 2
    else:
        cnt_pos = cnt_neg = 0

    return img, cnt_pos, cnt_neg


def generate_image_sources(
    room: Room,
    source: tuple[float, float, float],
    receiver: tuple[float, float, float],
    max_order: int = 8,
    c: float = 343.0,
) -> list[dict]:
    sx, sy, sz = source
    rx, ry, rz = receiver

    sources = []

    for px in range(-max_order, max_order + 1):
        x_img, cnt_x_pos, cnt_x_neg = _image_position(sx, room.largo, px)
        xi, xf = cnt_x_neg, cnt_x_pos

        for py in range(-max_order, max_order + 1):
            y_img, cnt_y_pos, cnt_y_neg = _image_position(sy, room.ancho, py)
            yi, yd = cnt_y_neg, cnt_y_pos

            for pz in range(-max_order, max_order + 1):
                z_img, cnt_z_pos, cnt_z_neg = _image_position(sz, room.alto, pz)
                zi, zs = cnt_z_neg, cnt_z_pos

                total_order = abs(px) + abs(py) + abs(pz)
                if total_order == 0:
                    continue

                dx = x_img - rx
                dy = y_img - ry
                dz = z_img - rz
                dist = math.sqrt(dx * dx + dy * dy + dz * dz)
                delay = dist / c

                reflection_counts = {
                    room.superficies[0].nombre: xi,  # frente (x=0)
                    room.superficies[1].nombre: xf,  # contrafrente (x=L)
                    room.superficies[2].nombre: yi,  # lat izq (y=0)
                    room.superficies[3].nombre: yd,  # lat der (y=W)
                    room.superficies[4].nombre: zi,  # piso (z=0)
                    room.superficies[5].nombre: zs,  # techo (z=H)
                }

                sources.append({
                    "position": (round(x_img, 4), round(y_img, 4), round(z_img, 4)),
                    "delay": round(delay, 6),
                    "distance": round(dist, 4),
                    "total_order": total_order,
                    "reflection_counts": reflection_counts,
                })

    sources.sort(key=lambda s: s["delay"])
    return sources


def calculate_energy(
    sources: list[dict],
    room: Room,
    banda: str,
) -> list[dict]:
    """Asigna energía a cada fuente imagen según absorción de paredes"""
    result = []
    for src in sources:
        energy = 1.0
        for i, sup in enumerate(room.superficies):
            count = src["reflection_counts"].get(sup.nombre, 0)
            alpha = sup.material.alpha.get(banda, 0)
            if count > 0:
                energy *= (1 - alpha) ** count
        src["energy"] = energy
        result.append(src)
    return result


def build_impulse_response(
    sources: list[dict],
    fs: int = 44100,
    duration_s: float = 1.0,
    banda_energia: Optional[str] = None,
    room: Optional[Room] = None,
) -> dict:
    n_samples = int(fs * duration_s)
    ir = [0.0] * n_samples

    direct_delay = sources[0]["delay"] if sources else 0

    for src in sources:
        sample = int(src["delay"] * fs)
        if sample >= n_samples:
            continue
        energy = src.get("energy", 1.0)
        amplitude = math.sqrt(energy) if energy > 0 else 0
        # Gaussian spreading for realistic IR
        spread = max(1, int(fs * 0.0005))
        for s in range(max(0, sample - spread), min(n_samples, sample + spread + 1)):
            gauss = math.exp(-((s - sample) ** 2) / (2 * spread ** 2))
            ir[s] += amplitude * gauss * 0.5

    max_amp = max(abs(v) for v in ir) if ir else 1
    if max_amp > 0:
        ir = [v / max_amp for v in ir]

    return {
        "impulse_response": ir,
        "sample_rate": fs,
        "direct_delay_ms": round(direct_delay * 1000, 2),
    }


def schroeder_integration(ir: list[float], fs: int) -> list[float]:
    """Integración inversa de Schroeder: E(t) = ∫_t^∞ p²(τ)dτ"""
    p2 = [v * v for v in ir]
    total_energy = sum(p2)
    decay = [0.0] * len(ir)
    cumulative = 0.0
    for i in range(len(ir) - 1, -1, -1):
        cumulative += p2[i]
        decay[i] = 10 * math.log10(max(cumulative / max(total_energy, 1e-10), 1e-10))
    return decay


def _linear_regression_db(
    decay: list[float], fs: int,
    start_db: float = -5, end_db: float = -35,
) -> float:
    """Encuentra la pendiente del decaimiento en un rango de dB"""
    samples = len(decay)
    indices = []
    values = []
    for i in range(samples):
        if start_db >= decay[i] >= end_db:
            indices.append(i)
            values.append(decay[i])

    if len(indices) < 3:
        return 0.0

    n = len(indices)
    sum_x = sum(indices)
    sum_y = sum(values)
    sum_xy = sum(indices[i] * values[i] for i in range(n))
    sum_x2 = sum(x * x for x in indices)

    denom = n * sum_x2 - sum_x * sum_x
    if abs(denom) < 1e-10:
        return 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    if slope >= 0:
        return 0.0

    rt60 = -60 / (slope * fs)
    return round(rt60, 2)


def calculate_iso3382_parameters(
    ir: list[float],
    fs: int,
    direct_delay_ms: float = 0,
) -> dict:
    ir_p2 = [v * v for v in ir]
    total_energy = sum(ir_p2)
    if total_energy <= 0:
        return {"error": "Sin energía en la respuesta al impulso"}

    # EDT (Early Decay Time): pendiente de los primeros 10 dB
    decay = schroeder_integration(ir, fs)
    edt = _linear_regression_db(decay, fs, -5, -15)

    # T20, T30
    t20 = _linear_regression_db(decay, fs, -5, -25)
    t30 = _linear_regression_db(decay, fs, -5, -35)

    # Early-to-late energy ratios
    def energy_upto(ms: float) -> float:
        samples = int(ms * fs / 1000)
        return sum(ir_p2[:samples])

    def energy_from(ms: float) -> float:
        samples = int(ms * fs / 1000)
        return sum(ir_p2[samples:])

    e80_early = energy_upto(80)
    e80_late = energy_from(80)
    c80 = round(10 * math.log10(max(e80_early / max(e80_late, 1e-10), 1e-10)), 1)

    e50_early = energy_upto(50)
    e50_late = energy_from(50)
    c50 = round(10 * math.log10(max(e50_early / max(e50_late, 1e-10), 1e-10)), 1)

    # D50 (Definition)
    d50 = round(e50_early / total_energy * 100, 1)

    # Ts (Center Time)
    ts_num = sum(i / fs * ir_p2[i] for i in range(len(ir_p2)))
    ts = round(ts_num / max(total_energy, 1e-10) * 1000, 1)

    # ITDG (Initial Time Delay Gap)
    # Buscar el pico del directo y la primera reflexión
    direct_sample = int(direct_delay_ms * fs / 1000)
    threshold = max(ir) * 0.1
    first_reflection = None
    for i in range(direct_sample + int(fs * 0.001), len(ir)):
        if ir[i] > threshold:
            first_reflection = i
            break
    itdg = round((first_reflection - direct_sample) / fs * 1000, 1) if first_reflection else None

    # Flutter echo detection (autocorrelation in late part)
    late_start = int(0.1 * fs)
    late_ir = ir[late_start:late_start + int(0.5 * fs)]
    flutter_detected = False
    flutter_freq = None
    if len(late_ir) > fs // 20:
        autocorr = [
            sum(late_ir[i] * late_ir[i + lag] for i in range(len(late_ir) - lag))
            for lag in range(1, min(int(0.05 * fs), len(late_ir) // 2))
        ]
        if autocorr:
            max_corr = max(autocorr)
            if max_corr > sum(autocorr) / len(autocorr) * 3:
                peak_lag = autocorr.index(max_corr) + 1
                flutter_freq = round(fs / peak_lag, 1)
                flutter_detected = True

    return {
        "EDT": edt,
        "T20": t20,
        "T30": t30,
        "C80": c80,
        "C50": c50,
        "D50": d50,
        "Ts": ts,
        "ITDG": itdg,
        "flutter_echo": {
            "detected": flutter_detected,
            "frequency": flutter_freq,
        },
    }

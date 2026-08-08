import math
import struct
import io
from .models import BANDAS_OCTAVA, Material, Room, Surface
from .presets import MATERIALES_PRESETS
from .reverberation import calculate_rt60, rt60_sabine

C = 343.0


def generate_ess(
    f1_hz: float = 20.0,
    f2_hz: float = 20000.0,
    duration_s: float = 5.0,
    sample_rate: int = 44100,
    amplitude: float = 0.9,
) -> list[float]:
    n_samples = int(sample_rate * duration_s)
    L = duration_s / math.log(f2_hz / f1_hz)
    signal = []
    for i in range(n_samples):
        t = i / sample_rate
        val = amplitude * math.sin(2 * math.pi * f1_hz * L * (math.exp(t / L) - 1))
        signal.append(round(val, 6))
    return signal


def inverse_filter(ess: list[float], sample_rate: int) -> list[float]:
    inv = ess[::-1]
    env = [1.0] * len(inv)
    n = len(inv)
    for i in range(n):
        t = i / sample_rate
        env[i] = math.exp(-t * 0.01)
    return [inv[i] * env[i] for i in range(n)]


def convolve(a: list[float], b: list[float]) -> list[float]:
    n = len(a) + len(b) - 1
    result = [0.0] * n
    for i in range(len(a)):
        ai = a[i]
        if ai == 0:
            continue
        for j in range(len(b)):
            result[i + j] += ai * b[j]
    return result


def ess_deconvolution(
    response: list[float],
    ess: list[float],
    sample_rate: int,
) -> list[float]:
    inv = inverse_filter(ess, sample_rate)
    ir = convolve(response, inv)
    peak = max(abs(v) for v in ir) or 1
    return [v / peak for v in ir]


def generate_wav_bytes(signal: list[float], sample_rate: int = 44100) -> bytes:
    n_samples = len(signal)
    data_size = n_samples * 2
    buf = io.BytesIO()
    buf.write(b'RIFF')
    buf.write(struct.pack('<I', 36 + data_size))
    buf.write(b'WAVE')
    buf.write(b'fmt ')
    buf.write(struct.pack('<I', 16))
    buf.write(struct.pack('<H', 1))
    buf.write(struct.pack('<H', 1))
    buf.write(struct.pack('<I', sample_rate))
    buf.write(struct.pack('<I', sample_rate * 2))
    buf.write(struct.pack('<H', 2))
    buf.write(struct.pack('<H', 16))
    for s in signal:
        s_int = max(-32768, min(32767, int(s * 32767)))
        buf.write(struct.pack('<h', s_int))
    return buf.getvalue()


def _biquad_bp(fc: float, fs: float, q: float = 4.0) -> tuple[float, float, float, float, float]:
    w0 = 2 * math.pi * fc / fs
    alpha = math.sin(w0) / (2 * q)
    b0 = alpha
    b1 = 0
    b2 = -alpha
    a0 = 1 + alpha
    a1 = -2 * math.cos(w0)
    a2 = 1 - alpha
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _apply_biquad(signal: list[float], b0: float, b1: float, b2: float, a1: float, a2: float) -> list[float]:
    x1 = x2 = y1 = y2 = 0.0
    out = [0.0] * len(signal)
    for i, x in enumerate(signal):
        y = b0 * x + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        out[i] = y
        x2 = x1
        x1 = x
        y2 = y1
        y1 = y
    return out


def compute_waterfall(
    ir: list[float],
    sample_rate: int,
    duration_s: float = 1.0,
) -> dict:
    n = int(sample_rate * duration_s)
    if len(ir) < n:
        ir = ir + [0.0] * (n - len(ir))
    ir = ir[:n]

    time_axis = [round(i / sample_rate * 1000, 1) for i in range(0, n, int(sample_rate / 100))]

    waterfall: dict[str, list[float]] = {}
    for b in BANDAS_OCTAVA:
        fc = float(b)
        b0, b1, b2, a1, a2 = _biquad_bp(fc, sample_rate)
        filtered = _apply_biquad(ir, b0, b1, b2, a1, a2)
        sq = [v * v for v in filtered]
        decay = [0.0] * (n // (int(sample_rate / 100)))
        total = sum(sq)
        running = total
        for i in range(len(decay)):
            idx = i * (int(sample_rate / 100))
            if running > 0:
                decay[i] = round(10 * math.log10(running / total), 2) if total > 0 else -60
            else:
                decay[i] = -60
            for j in range(min(int(sample_rate / 100), n - idx)):
                running -= sq[idx + j] if idx + j < len(sq) else 0
        waterfall[b] = decay

    return {
        "time_ms": time_axis,
        "bands": waterfall,
        "sample_rate": sample_rate,
        "duration_s": duration_s,
    }


def calibrate_alpha(
    room: Room,
    measured_rt60: dict[str, float],
    iterations: int = 30,
    learning_rate: float = 0.05,
) -> dict:
    calibrated: dict[str, dict[str, float]] = {}
    for b in BANDAS_OCTAVA:
        measured = measured_rt60.get(b, 0.5)
        if measured <= 0:
            continue
        adj = {s.nombre: s.material.alpha.get(b, 0.1) for s in room.superficies}
        for _ in range(iterations):
            test_surfaces = [
                Surface(
                    nombre=s.nombre,
                    area=s.area,
                    material=Material(nombre="adj", alpha_unico=adj[s.nombre]),
                )
                for s in room.superficies
            ]
            test_room = Room(
                largo=room.largo, ancho=room.ancho, alto=room.alto,
                superficies=test_surfaces,
            )
            predicted = rt60_sabine(test_room, b)
            if predicted == float('inf'):
                break
            error = predicted - measured
            for s in room.superficies:
                adj[s.nombre] -= learning_rate * error * 0.01 * adj[s.nombre]
                adj[s.nombre] = max(0.01, min(0.99, adj[s.nombre]))
        calibrated[b] = {name: round(val, 4) for name, val in adj.items()}
    return calibrated

import math
from .models import Room, BANDAS_OCTAVA


def _absorcion_total(room: Room, banda: str) -> float:
    return sum(p.area * p.material.alpha.get(banda, 0) for p in room.superficies)


def _a_promedio(room: Room, banda: str) -> float:
    return _absorcion_total(room, banda) / room.superficie_total


def rt60_sabine(room: Room, banda: str) -> float:
    A = _absorcion_total(room, banda)
    if A <= 0:
        return float('inf')
    valor = 0.161 * room.volumen / A
    return round(valor, 2)


def rt60_eyring(room: Room, banda: str) -> float:
    S = room.superficie_total
    alpha = _a_promedio(room, banda)
    if alpha >= 1:
        return 0.0
    if alpha <= 0:
        return float('inf')
    valor = (0.161 * room.volumen) / (-S * math.log(1 - alpha))
    return round(valor, 2)


def rt60_millington(room: Room, banda: str) -> float:
    A = sum(
        -p.area * math.log(max(1 - p.material.alpha.get(banda, 0), 1e-10))
        for p in room.superficies
    )
    if A <= 0:
        return float('inf')
    valor = 0.161 * room.volumen / A
    return round(valor, 2)


def rt60_fitzroy(room: Room, banda: str) -> float:
    def T(s, a):
        if a >= 1:
            return 0.0
        if a <= 0:
            return float('inf')
        return s / (-math.log(1 - a))

    sx = room.superficies[0].area + room.superficies[1].area
    sy = room.superficies[2].area + room.superficies[3].area
    sz = room.superficies[4].area + room.superficies[5].area
    ax = (room.superficies[0].material.alpha.get(banda, 0) + room.superficies[1].material.alpha.get(banda, 0)) / 2
    ay = (room.superficies[2].material.alpha.get(banda, 0) + room.superficies[3].material.alpha.get(banda, 0)) / 2
    az = (room.superficies[4].material.alpha.get(banda, 0) + room.superficies[5].material.alpha.get(banda, 0)) / 2
    s_total = room.superficie_total

    if s_total <= 0:
        return 0.0
    valor = (0.161 * room.volumen * (T(sx, ax) + T(sy, ay) + T(sz, az))) / (s_total ** 2)
    return round(valor, 2)


def calculate_rt60(room: Room) -> dict[str, dict[str, float]]:
    resultado = {}
    for banda in BANDAS_OCTAVA:
        resultado[banda] = {
            "Sabine": rt60_sabine(room, banda),
            "Eyring": rt60_eyring(room, banda),
            "Millington": rt60_millington(room, banda),
            "FitzRoy": rt60_fitzroy(room, banda),
        }
    return resultado


def rt60_promedio_sabine(room: Room) -> float:
    alfas = []
    for p in room.superficies:
        vals = list(p.material.alpha.values())
        alfas.append(sum(vals) / len(vals))
    S_total = room.superficie_total
    A_total = sum(room.superficies[i].area * alfas[i] for i in range(6))
    if A_total <= 0:
        return float('inf')
    return round(0.161 * room.volumen / A_total, 2)

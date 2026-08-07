import math
from itertools import product
from .models import Room, Mode, ModeType


def classify_mode(nx: int, ny: int, nz: int) -> tuple[ModeType, float]:
    non_zero = sum(1 for n in (nx, ny, nz) if n > 0)
    if non_zero == 1:
        return ModeType.AXIAL, 0.0
    if non_zero == 2:
        return ModeType.TANGENTIAL, -3.0
    return ModeType.OBLIQUE, -6.0


def calculate_modes(room: Room, max_order: int = 5) -> list[Mode]:
    c = 343.0
    combinaciones = list(product(range(max_order), repeat=3))
    combinaciones.remove((0, 0, 0))

    modos = []
    for nx, ny, nz in combinaciones:
        x = (nx / room.largo) ** 2
        y = (ny / room.ancho) ** 2
        z = (nz / room.alto) ** 2
        frecuencia = round((c / 2) * math.sqrt(x + y + z), 1)

        tipo, peso = classify_mode(nx, ny, nz)
        modos.append(Mode(
            indices=[nx, ny, nz],
            frecuencia=frecuencia,
            tipo=tipo,
            peso_db=peso,
        ))

    modos.sort(key=lambda m: m.frecuencia)
    return modos


def detect_degenerate_modes(modos: list[Mode], tolerance: float = 0.1) -> list[Mode]:
    vistos: dict[float, list[int]] = {}
    for i, modo in enumerate(modos):
        vistos.setdefault(modo.frecuencia, []).append(i)
    for indices in vistos.values():
        if len(indices) > 1:
            for i in indices:
                modos[i].degenerado = True
    return modos


def detect_overlapping_modes(modos: list[Mode], delta_f: float) -> list[Mode]:
    for i in range(len(modos) - 1):
        if abs(modos[i + 1].frecuencia - modos[i].frecuencia) < delta_f:
            modos[i].solapado = True
            modos[i + 1].solapado = True
    return modos

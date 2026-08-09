import math
from itertools import product

from .environment import Environment
from .models import Room, Mode, ModeType


def classify_mode(nx: int, ny: int, nz: int) -> tuple[ModeType, float]:
    indices = (nx, ny, nz)
    if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in indices):
        raise ValueError("modal indices must be non-negative integers")
    non_zero = sum(1 for n in (nx, ny, nz) if n > 0)
    if non_zero == 0:
        raise ValueError("(0, 0, 0) is not a physical room mode")
    if non_zero == 1:
        return ModeType.AXIAL, 0.0
    if non_zero == 2:
        return ModeType.TANGENTIAL, -3.0
    return ModeType.OBLIQUE, -6.0


def _sound_speed(room: Room, c: float | None, environment: Environment | None) -> float:
    if c is not None:
        if isinstance(c, bool) or not isinstance(c, (int, float)):
            raise TypeError("c must be a real number")
        speed = float(c)
        if not math.isfinite(speed) or speed <= 0.0:
            raise ValueError("c must be finite and positive")
        return speed
    return (environment or room.environment).sound_speed_m_s


def calculate_modes(
    room: Room,
    max_order: int | None = None,
    f_max: float | None = None,
    *,
    c: float | None = None,
    environment: Environment | None = None,
) -> list[Mode]:
    """Enumerate rectangular-room modes.

    An explicitly supplied ``max_order`` is inclusive on every axis.  With no
    bound the historical default is retained (orders 0 through 4, 124 modes).
    Supplying ``f_max`` instead derives sufficient per-axis orders and returns
    every mode at or below that frequency.
    """

    if max_order is not None and f_max is not None:
        raise ValueError("provide either max_order or f_max, not both")
    speed = _sound_speed(room, c, environment)

    if f_max is not None:
        if isinstance(f_max, bool) or not isinstance(f_max, (int, float)):
            raise TypeError("f_max must be a real number")
        f_max = float(f_max)
        if not math.isfinite(f_max) or f_max <= 0.0:
            raise ValueError("f_max must be finite and positive")
        limits = (
            math.floor(2.0 * room.largo * f_max / speed),
            math.floor(2.0 * room.ancho * f_max / speed),
            math.floor(2.0 * room.alto * f_max / speed),
        )
    else:
        if max_order is None:
            max_order = 4
        if isinstance(max_order, bool) or not isinstance(max_order, int) or max_order < 0:
            raise ValueError("max_order must be a non-negative integer")
        limits = (max_order, max_order, max_order)

    modos: list[Mode] = []
    combinations = product(*(range(limit + 1) for limit in limits))
    for nx, ny, nz in combinations:
        if (nx, ny, nz) == (0, 0, 0):
            continue
        x = (nx / room.largo) ** 2
        y = (ny / room.ancho) ** 2
        z = (nz / room.alto) ** 2
        frecuencia = (speed / 2.0) * math.sqrt(x + y + z)
        if f_max is not None and frecuencia > f_max:
            continue

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
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise ValueError("tolerance must be finite and non-negative")
    for modo in modos:
        modo.degenerado = False
        modo.multiplicity = 1
        modo.degeneracy_cluster = None

    ordered = sorted(range(len(modos)), key=lambda index: modos[index].frecuencia)
    cluster_id = 0
    start = 0
    while start < len(ordered):
        anchor_frequency = modos[ordered[start]].frecuencia
        end = start + 1
        while (
            end < len(ordered)
            and modos[ordered[end]].frecuencia - anchor_frequency <= tolerance
        ):
            end += 1
        members = ordered[start:end]
        if len(members) > 1:
            for index in members:
                modos[index].degenerado = True
                modos[index].multiplicity = len(members)
                modos[index].degeneracy_cluster = cluster_id
            cluster_id += 1
        start = end
    return modos


def detect_overlapping_modes(modos: list[Mode], delta_f: float) -> list[Mode]:
    if not math.isfinite(delta_f) or delta_f < 0.0:
        raise ValueError("delta_f must be finite and non-negative")
    for modo in modos:
        modo.solapado = False
        modo.overlap_multiplicity = 1
        modo.overlap_cluster = None

    ordered = sorted(range(len(modos)), key=lambda index: modos[index].frecuencia)
    cluster_id = 0
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered):
            previous = modos[ordered[end - 1]].frecuencia
            current = modos[ordered[end]].frecuencia
            if current - previous > delta_f:
                break
            end += 1
        members = ordered[start:end]
        if len(members) > 1:
            for index in members:
                modos[index].solapado = True
                modos[index].overlap_cluster = cluster_id
            cluster_id += 1
        start = end

    # A connected chain is not necessarily simultaneous overlap.  Multiplicity
    # is the largest number of modal centers sharing any window of width delta_f.
    left = 0
    for right in range(len(ordered)):
        while (
            left < right
            and modos[ordered[right]].frecuencia - modos[ordered[left]].frecuencia > delta_f
        ):
            left += 1
        multiplicity = right - left + 1
        if multiplicity > 1:
            for position in range(left, right + 1):
                index = ordered[position]
                modos[index].overlap_multiplicity = max(
                    modos[index].overlap_multiplicity,
                    multiplicity,
                )
    return modos

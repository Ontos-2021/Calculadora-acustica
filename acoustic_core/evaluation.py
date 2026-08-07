import math
from .models import Room, Mode, ModeType, BANDAS_OCTAVA
from .resonance import calculate_modes


def calculate_schroeder(rt60_sabine: float, volumen: float) -> float:
    if rt60_sabine <= 0 or volumen <= 0:
        return 0.0
    return round(2000 * math.sqrt(rt60_sabine / volumen), 1)


def calculate_modal_bandwidth(rt60_sabine: float) -> float:
    if rt60_sabine <= 0:
        return 0.0
    return round(2.2 / rt60_sabine, 2)


def evaluate_bonello(frecuencias: list[float]) -> dict:
    n = 125
    bandas: dict[float, list[float]] = {}
    for banda_idx in range(-8, 23):
        central = n * (2 ** (banda_idx / 3))
        bandas[central] = []

    for freq in frecuencias:
        for central in sorted(bandas.keys()):
            if freq < central:
                bandas[central].append(freq)
                break

    resultado = {}
    for freq_central, modos in sorted(bandas.items()):
        if freq_central < 500 or len(modos) != 0:
            resultado[round(freq_central, 1)] = len(modos)

    counts = list(resultado.values())
    violaciones = []
    for i in range(1, len(counts)):
        if counts[i] < counts[i - 1]:
            violaciones.append(i)

    return {
        "cumple": len(violaciones) == 0,
        "bandas": resultado,
        "violaciones": violaciones,
        "total_modos": sum(counts),
    }


def find_degenerate_dimensions(largo: float, ancho: float, alto: float) -> list[str]:
    advertencias = []
    dims = [("Largo", largo), ("Ancho", ancho), ("Alto", alto)]
    for i, (n1, v1) in enumerate(dims):
        for j, (n2, v2) in enumerate(dims):
            if i >= j:
                continue
            if abs(v1 - v2) < 0.01:
                advertencias.append(f"{n1} ≈ {n2} ({v1:.2f} m): dimensiones iguales -> alta degeneración modal")
            elif abs(v1 / v2 - round(v1 / v2)) < 0.01 and v1 > v2:
                ratio = round(v1 / v2)
                advertencias.append(f"{n1} es múltiplo entero de {n2} ({ratio}x): puede causar modos degenerados")
    return advertencias


def get_mode_distribution(modos: list[Mode]) -> dict:
    tipos = {t: 0 for t in ModeType}
    for m in modos:
        tipos[m.tipo] += 1
    return {
        "axiales": tipos[ModeType.AXIAL],
        "tangenciales": tipos[ModeType.TANGENTIAL],
        "oblicuos": tipos[ModeType.OBLIQUE],
        "degenerados": sum(1 for m in modos if m.degenerado),
        "solapados": sum(1 for m in modos if m.solapado),
    }

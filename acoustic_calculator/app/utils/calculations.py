import math
from typing import List, Dict, Union

Number = Union[int, float]


def combine_modes(n: int) -> List[List[int]]:
    combinaciones: List[List[int]] = []

    def combinar(nx: int, ny: int, nz: int) -> None:
        if nz == n:
            if ny == n:
                if nx == n:
                    return
                else:
                    nx += 1
                    ny = 0
                    nz = 0
            else:
                ny += 1
                nz = 0
        else:
            nz += 1
        combinaciones.append([nx, ny, nz])
        combinar(nx, ny, nz)

    combinar(0, 0, 0)
    return combinaciones


def calculate_resonance_modes(largo: Number, ancho: Number, alto: Number) -> Dict:
    n = 5
    combinaciones = combine_modes(n)
    modos = []

    def frecuencia_modal(combinacion: List[int], l: Number, a: Number, h: Number) -> float:
        nx, ny, nz = combinacion
        x = (nx / l) ** 2
        y = (ny / a) ** 2
        z = (nz / h) ** 2
        xyz = (x + y + z) ** 0.5
        return round((343 / 2) * xyz, 1)

    for combinacion in combinaciones:
        frecuencia = frecuencia_modal(combinacion, largo, ancho, alto)
        modos.append({'combinacion': combinacion, 'frecuencia': frecuencia})

    modos.sort(key=lambda modo: modo['frecuencia'])
    frecuencias = [modo['frecuencia'] for modo in modos]

    return {'modos': modos, 'frequencies': frecuencias}


def calculate_rt60(largo: Number, ancho: Number, alto: Number, alfas: List[float]) -> Dict[str, float]:
    volumen = largo * ancho * alto
    superficies = [
        ancho * alto,   # Frente
        ancho * alto,   # Contrafrente
        largo * alto,   # Lateral Izquierdo
        largo * alto,   # Lateral Derecho
        largo * ancho,  # Piso
        largo * ancho,  # Techo
    ]

    paredes = [{"Superficie": superficies[i], "Alfa": alfas[i]} for i in range(6)]

    def sabine(vol: float) -> float:
        A_total = sum(p["Superficie"] * p["Alfa"] for p in paredes)
        return float(round((0.161 * vol / A_total) * 1000, 1))

    def eyring(vol: float) -> float:
        A_total = sum(p["Superficie"] * p["Alfa"] for p in paredes)
        S_total = sum(p["Superficie"] for p in paredes)
        return float(
            round((0.161 * vol) / (-S_total * math.log(1 - (A_total / S_total))) * 1000, 1))

    def millington(vol: float) -> float:
        A_total = sum(-p["Superficie"] * math.log(1 - p["Alfa"]) for p in paredes)
        return float(round((0.161 * vol / A_total) * 1000, 1))

    def fitz_roy(vol: float) -> float:
        def T(s: float, a: float) -> float:
            return s / -(math.log(1 - a))

        sx = paredes[0]["Superficie"] + paredes[1]["Superficie"]
        sy = paredes[2]["Superficie"] + paredes[3]["Superficie"]
        sz = paredes[4]["Superficie"] + paredes[5]["Superficie"]
        ax = (paredes[0]["Alfa"] + paredes[1]["Alfa"]) / 2
        ay = (paredes[2]["Alfa"] + paredes[3]["Alfa"]) / 2
        az = (paredes[4]["Alfa"] + paredes[5]["Alfa"]) / 2
        s_total = sum(superficies)
        return round(((0.161 * vol * (T(sx, ax) + T(sy, ay) + T(sz, az))) / s_total ** 2) * 1000, 1)

    return {
        'Sabine': sabine(volumen),
        'Eyring': eyring(volumen),
        'Millington': millington(volumen),
        'Fitz Roy': fitz_roy(volumen),
    }

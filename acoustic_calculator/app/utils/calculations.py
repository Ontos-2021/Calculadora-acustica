import math


def combine_modes(n):
    combinaciones = []

    def combinar(nx, ny, nz):
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


def calculate_resonance_modes(largo, ancho, alto):
    n = 3
    combinaciones = combine_modes(n)
    modos = []

    def frecuencia_modal(combinacion, largo, ancho, alto):
        nx, ny, nz = combinacion
        x = (nx / largo) ** 2
        y = (ny / ancho) ** 2
        z = (nz / alto) ** 2
        xyz = (x + y + z) ** 0.5  # Convertimos a float directamente
        return round((343 / 2) * xyz, 1)

    for combinacion in combinaciones:
        frecuencia = frecuencia_modal(combinacion, largo, ancho, alto)
        modo = {'combinacion': combinacion, 'frecuencia': frecuencia}
        modos.append(modo)

    modos.sort(key=lambda modo: modo['frecuencia'], reverse=False)
    frecuencias = [modo['frecuencia'] for modo in modos]

    return {'modos': modos, 'frequencies': frecuencias}


def calculate_rt60(largo, ancho, alto, alfas):
    volumen = largo * ancho * alto
    superficies = [
        largo * ancho,  # Techo
        largo * ancho,  # Piso
        largo * alto,  # Lateral Derecho
        largo * alto,  # Lateral Izquierdo
        ancho * alto,  # Frente
        ancho * alto  # Contrafrente
    ]

    paredes = [{"Superficie": superficies[i], "Alfa": alfas[i]} for i in range(6)]

    def sabine(volumen):
        A_total = sum([pared["Superficie"] * pared["Alfa"] for pared in paredes])
        return float(round((0.161 * volumen / A_total) * 1000, 1))

    def eyring(volumen):
        A_total = sum([pared["Superficie"] * pared["Alfa"] for pared in paredes])
        superficie_total = sum([pared["Superficie"] for pared in paredes])
        return float(
            round((0.161 * volumen) / (-1 * superficie_total * math.log(1 - (A_total / superficie_total))) * 1000, 1))

    def millington(volumen):
        A_total = sum([-pared["Superficie"] * math.log(1 - pared["Alfa"]) for pared in paredes])
        return float(round((0.161 * volumen / A_total) * 1000, 1))

    def fitz_roy(volumen):
        def T(s, a):
            return s / -(math.log(1 - a))

        sx = (paredes[0]["Superficie"] + paredes[1]["Superficie"])
        sy = (paredes[2]["Superficie"] + paredes[3]["Superficie"])
        sz = (paredes[4]["Superficie"] + paredes[5]["Superficie"])
        ax = ((paredes[0]["Alfa"] + paredes[1]["Alfa"]) / 2)
        ay = ((paredes[2]["Alfa"] + paredes[3]["Alfa"]) / 2)
        az = ((paredes[4]["Alfa"] + paredes[5]["Alfa"]) / 2)
        return round(((0.161 * volumen * (T(sx, ax) + T(sy, ay) + T(sz, az))) / sum(superficies) ** 2) * 1000, 1)

    return {
        'Sabine': sabine(volumen),
        'Eyring': eyring(volumen),
        'Millington': millington(volumen),
        'Fitz Roy': fitz_roy(volumen)
    }

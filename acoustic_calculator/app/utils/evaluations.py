from typing import Dict, List, Union

Number = Union[int, float]


def criterio_de_bonello(frecuencias: List[Number]) -> Dict[float, int]:
    bandas_de_frecuencia: Dict[float, list] = {}
    n = 125

    for banda in range(-8, 23):
        bandas_de_frecuencia[n * (2 ** (banda / 3))] = []

    for frecuencia in frecuencias:
        for banda in bandas_de_frecuencia:
            if frecuencia < banda:
                bandas_de_frecuencia[banda].append(frecuencia)
                break

    resultado_bonello = {}
    for banda_de_frecuencia in bandas_de_frecuencia:
        if banda_de_frecuencia < 500 or len(bandas_de_frecuencia[banda_de_frecuencia]) != 0:
            resultado_bonello[round(banda_de_frecuencia, 1)] = len(bandas_de_frecuencia[banda_de_frecuencia])

    return resultado_bonello

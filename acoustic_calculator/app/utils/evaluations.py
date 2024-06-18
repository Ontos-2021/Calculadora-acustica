def criterio_de_bonello(frecuencias):
    # Inicializar un diccionario para las bandas de frecuencia
    bandas_de_frecuencia = {}
    n = 125

    # Crear las bandas de frecuencia
    for banda in range(-8, 23):
        bandas_de_frecuencia[n * (2 ** (banda / 3))] = []

    # Clasificar las frecuencias en las bandas de frecuencia
    for frecuencia in frecuencias:
        for banda in bandas_de_frecuencia:
            if frecuencia < banda:
                bandas_de_frecuencia[banda].append(frecuencia)
                break

    # Evaluar y mostrar el criterio de Bonello
    banda_anterior = 0
    tercios = {}
    data_grafico_barra = {}

    resultado_bonello = {}
    for banda_de_frecuencia in bandas_de_frecuencia:
        if banda_de_frecuencia < 500 or len(bandas_de_frecuencia[banda_de_frecuencia]) != 0:
            resultado_bonello[round(banda_de_frecuencia, 1)] = len(bandas_de_frecuencia[banda_de_frecuencia])

    return resultado_bonello

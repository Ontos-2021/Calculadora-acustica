import decimal
import math
from tkinter import *
from tkinter import ttk

""""Velocidad del sonido = 331.3m/s + 0.6 x temperatura"""


class ModoResonancia:

    def __init__(self, combinacion, frecuencia):
        self.combinacion = combinacion
        self.frecuencia = frecuencia
        contadorZero = 0
        for numero in self.combinacion:
            if numero == 0:
                contadorZero += 1

        self.tipo = self.obtenerTipo(contadorZero)

    def __str__(self):
        return f"Para la combinación {self.combinacion} la cual es un modo {self.tipo} la frecuencia es {self.frecuencia}"

    def obtenerTipo(self, cantidadZeros):
        return {
            0: 'Oblicuo',
            1: 'Tangencial',
            2: 'Axial'
        }.get(cantidadZeros, '')


def calcular():
    # Modos de Resonancia

    n = 5
    # n = int(input("Dame el n: "))
    combinaciones = []
    frecuencias_por_combinaciones = {}
    modos = []

    def combinar(nx, ny, nz):
        if nz == n:
            if ny == n:
                if nx == n:
                    return 0
                    pass
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
        return combinar(nx, ny, nz)

    combinar(0, 0, 0)

    def frecuencia_modal(combinacion, largo, ancho, alto):
        nx = combinacion[0]
        ny = combinacion[1]
        nz = combinacion[2]
        x = (nx / largo) ** 2
        y = (ny / ancho) ** 2
        z = (nz / alto) ** 2
        xyz = ((x + y + z) ** decimal.Decimal(0.5))
        return round((decimal.Decimal(343 / 2) * xyz), 1)

    # Calculo de RT60

    def fitz_roy(volumen):

        def T(s, a):
            return s / -(decimal.Decimal(math.log(1 - a)))

        sx = (paredes["Techo"]["Superficie"] + paredes["Piso"]["Superficie"])
        sy = (paredes["Lateral Derecho"]["Superficie"] + paredes["Lateral Izquierdo"]["Superficie"])
        sz = (paredes["Frente"]["Superficie"] + paredes["Contrafrente"]["Superficie"])
        ax = ((paredes["Techo"]["Alfa"] + paredes["Piso"]["Alfa"]) / 2)
        ay = ((paredes["Lateral Derecho"]["Alfa"] + paredes["Lateral Izquierdo"]["Alfa"]) / 2)
        az = ((paredes["Frente"]["Alfa"] + paredes["Contrafrente"]["Alfa"]) / 2)
        return round(((math.prod(
            (decimal.Decimal(0.161), volumen, (T(sx, ax) + T(sy, ay) + T(sz, az))))) / superficie_total ** 2) * 1000, 1)


    def millintong(volumen):

        A_total = 0
        for pared in paredes:
            pared_actual = paredes[pared]
            alfa_actual = pared_actual["Alfa"]
            superficie_actual = pared_actual["Superficie"]
            A_actual = decimal.Decimal(math.prod((-1, superficie_actual, decimal.Decimal(math.log(1 - alfa_actual)))))
            A_total += A_actual

        return float(
            round((float((math.prod((decimal.Decimal(0.161), decimal.Decimal(volumen))) / A_total))) * 1000, 1))

    def eyring(volumen):
        A_total = 0
        superficie_total = 0
        for pared in paredes:
            pared_actual = paredes[pared]
            alfa_actual = pared_actual["Alfa"]
            superficie_actual = pared_actual["Superficie"]
            superficie_total += superficie_actual
            A_actual = math.prod((superficie_actual, alfa_actual))
            A_total += A_actual

        return float(round(((math.prod((decimal.Decimal(0.161), decimal.Decimal(volumen)))) / (math.prod((
            decimal.Decimal(
                superficie_total),
            decimal.Decimal(
                (-1 * (
                    math.log(
                        1 - (
                                A_total / superficie_total)))))))) * 1000),
                           1))

    def sabine(volumen):
        A_total = 0
        for pared in paredes:
            pared_actual = paredes[pared]
            alfa_actual = pared_actual["Alfa"]
            superficie_actual = pared_actual["Superficie"]
            A_actual = math.prod((superficie_actual, alfa_actual))
            A_total += A_actual
        return float(round((float(((math.prod((decimal.Decimal(0.161), volumen))) / (A_total) * 1000))), 1))

    # Otras variables

    def f_room(volumen):
        rt = (decimal.Decimal(sabine(volumen)) / decimal.Decimal(1000))
        return decimal.Decimal(2000) * ((decimal.Decimal(rt) / volumen) ** decimal.Decimal(0.5))

    def criterio_de_bonello(frecuencias):
        # una lista de "rangos" de frecuencia. Cada valor representa el límite superior del rango
        bandas_de_frecuencia = {}
        n = 125
        for banda in range(-8, 23):
            bandas_de_frecuencia[n * (2 ** (banda / 3))] = []
        # Clasificar por bandas
        for frecuencia in frecuencias:
            for banda in bandas_de_frecuencia:
                if frecuencia < banda:
                    bandas_de_frecuencia[banda].append(frecuencia)
                    break
        # Display y creando una lista con el rango y número de modos
        bandaAnterior = 0
        tercios = {}
        data_grafico_barra = {}
        # frame_2_b.tree.insert("", "end", values=("", "", ""))
        for banda_de_frecuencia in bandas_de_frecuencia:
            if banda_de_frecuencia < 500 or len(bandas_de_frecuencia[banda_de_frecuencia]) != 0:
                mensaje1 = "Banda: " + str(bandaAnterior) + " - " + str(round(banda_de_frecuencia, 1))
                mensaje2 = str(len(bandas_de_frecuencia[banda_de_frecuencia]))
                frame_2_b.tree.insert("", "end", values=(mensaje1, mensaje2, ""))
                bandaAnterior = round(banda_de_frecuencia, 1)
                data_grafico_barra[round(banda_de_frecuencia, 1)] = len(bandas_de_frecuencia[banda_de_frecuencia])
                # print(mensaje1)
                # print(mensaje2)
                # print("")

    # Definición de variables

    lar = decimal.Decimal(largo_entrada.get())
    anc = decimal.Decimal(ancho_entrada.get())
    alt = decimal.Decimal(alto_entrada.get())
    a_1 = decimal.Decimal(alfa_entrada.get())
    a_2 = decimal.Decimal(alfa_2_entrada.get())
    a_3 = decimal.Decimal(alfa_3_entrada.get())
    a_4 = decimal.Decimal(alfa_4_entrada.get())
    a_5 = decimal.Decimal(alfa_5_entrada.get())
    a_6 = decimal.Decimal(alfa_6_entrada.get())

    # Paredes

    frente = {"Dimension 1": anc,
              "Dimension 2": alt,
              "Superficie": (math.prod((anc, alt))),
              "Alfa": a_1
              }
    contrafrente = {"Dimension 1": anc,
                    "Dimension 2": alt,
                    "Superficie": (math.prod((anc, alt))),
                    "Alfa": a_2
                    }
    lateral_izq = {"Dimension 1": lar,
                   "Dimension 2": alt,
                   "Superficie": (math.prod((lar, alt))),
                   "Alfa": a_3
                   }
    lateral_der = {"Dimension 1": lar,
                   "Dimension 2": alt,
                   "Superficie": (math.prod((lar, alt))),
                   "Alfa": a_4
                   }
    piso = {"Dimension 1": lar,
            "Dimension 2": anc,
            "Superficie": (math.prod((lar, anc))),
            "Alfa": a_5
            }
    techo = {"Dimension 1": lar,
             "Dimension 2": anc,
             "Superficie": (math.prod((lar, anc))),
             "Alfa": a_6
             }

    paredes = {"Frente": frente,
               "Contrafrente": contrafrente,
               "Lateral Izquierdo": lateral_izq,
               "Lateral Derecho": lateral_der,
               "Piso": piso,
               "Techo": techo
               }

    volumen = math.prod((alt, anc, lar))

    superficie_total = 0
    for pared in paredes:
        pared_actual = paredes[pared]
        superficie_total += (pared_actual["Superficie"])

    # Listas de Coeficiente de absorción

    coeficientes_de_absorcion = [a_1, a_2, a_3, a_4, a_5, a_6]

    """if max(coeficientes_de_absorcion) > 0.2:
        print(f"El máximo coeficiente de absorción es mayor a 0.2: {max(coeficientes_de_absorcion)}")
    else:
        print(f"El coeficiente de absorción máximo es menor a 0.2: {max(coeficientes_de_absorcion)}")"""

    alfa_superficie_paredes = [paredes["Frente"]["Alfa"] * paredes["Frente"]["Superficie"],
                               paredes["Contrafrente"]["Alfa"] * paredes["Contrafrente"]["Superficie"],
                               paredes["Lateral Izquierdo"]["Alfa"] * paredes["Lateral Izquierdo"]["Superficie"],
                               paredes["Lateral Derecho"]["Alfa"] * paredes["Lateral Derecho"]["Superficie"],
                               paredes["Piso"]["Alfa"] * paredes["Piso"]["Superficie"],
                               paredes["Techo"]["Alfa"] * paredes["Techo"]["Superficie"]]

    alfa_paredes_promedio = round(sum(alfa_superficie_paredes) / superficie_total, 2)

    # GUI - Interfaz (Tkinter)

    # Cleaning Table
    records = wind.tree.get_children()
    for element in records:
        wind.tree.delete(element)

    records = frame_2_a.tree.get_children()
    for element in records:
        frame_2_a.tree.delete(element)

    records = frame_2_b.tree.get_children()
    for element in records:
        frame_2_b.tree.delete(element)

    records = frame_3.tree.get_children()
    for element in records:
        frame_3.tree.delete(element)

    #  Escribiendo en la tabla

    for ficha in paredes:
        wind.tree.insert("", "end", values=(
            ficha, str((round(paredes[ficha]["Superficie"], 2))) + str(" m2"), paredes[ficha]["Alfa"]))

    frame_2_a.tree.insert("", "end", values=("Superficie Total", str(round(superficie_total, 1)) + str(" m2"), ""))
    frame_2_a.tree.insert("", "end", values=("Volumen", str(round(volumen, 1)) + str(" m3"), ""))

    frame_2_a.tree.insert("", "end", values=("Sabine", str(sabine(volumen)) + str(" ms"), ""))
    frame_2_a.tree.insert("", "end", values=("Eyring", str(eyring(volumen)) + str(" ms"), ""))
    frame_2_a.tree.insert("", "end", values=("Millintong", (str(millintong(volumen)) + str(" ms")), ""))
    frame_2_a.tree.insert("", "end", values=("Fitz Roy", str(fitz_roy(volumen)) + str(" ms"), ""))
    frame_2_a.tree.insert("", "end", values=("F-Room", str(round(f_room(volumen), 1)) + str(" Hz"), ""))
    frame_2_a.tree.insert("", "end", values=("Alfa promedio", alfa_paredes_promedio, ""))

    # Combinando

    for combinacion in combinaciones:
        # calcular frecuencia
        frecuencia = frecuencia_modal(combinacion, lar, anc, alt)
        modo = ModoResonancia(combinacion, frecuencia)
        modos.append(modo)

    modos.sort(key=lambda modo: modo.frecuencia, reverse=False)

    # Escribiendo los modos en la tabla
    frecuencias_bonello = []
    for modo in modos:
        frame_3.tree.insert("", "end", values=(modo.combinacion, str(modo.frecuencia) + str(" Hz"), modo.tipo))
        frecuencias_bonello.append(modo.frecuencia)

    criterio_de_bonello(frecuencias_bonello)


wind = Tk()
wind.title("Calculadora Acústica")
wind.geometry()

# Frame Variables

variables_frame = Frame(wind)
variables_frame.grid(row=0, column=0, columnspan=2)

#   Dimensiones y valores y botones

largo = Label(variables_frame, text="Largo (m)", justify="center").grid(row=0, column=0, pady=4, padx=10)
ancho = Label(variables_frame, text="Ancho (m)", justify="center").grid(row=1, column=0, pady=4, padx=10)
alto = Label(variables_frame, text="Alto (m)", justify="center").grid(row=2, column=0, pady=4, padx=10)
alfa_1 = Label(variables_frame, text="Alfa (Frente)", justify="center").grid(row=3, column=0, pady=4, padx=10)
alfa_2 = Label(variables_frame, text="Alfa (Contrafrente)", justify="center").grid(row=4, column=0, pady=4, padx=10)
alfa_3 = Label(variables_frame, text="Alfa (Lateral Izquierdo)", justify="center").grid(row=5, column=0, pady=4,
                                                                                        padx=10)
alfa_4 = Label(variables_frame, text="Alfa (Lateral Derecho)", justify="center").grid(row=6, column=0, pady=4, padx=10)
alfa_5 = Label(variables_frame, text="Alfa Piso", justify="center").grid(row=7, column=0, pady=4, padx=10)
alfa_6 = Label(variables_frame, text="Alfa Techo", justify="center").grid(row=8, column=0, pady=4, padx=10)

largo_entrada = Entry(variables_frame)
largo_entrada.grid(row=0, column=1)
largo_entrada.focus()

ancho_entrada = Entry(variables_frame)
ancho_entrada.grid(row=1, column=1)

alto_entrada = Entry(variables_frame)
alto_entrada.grid(row=2, column=1)

alfa_entrada = Entry(variables_frame)
alfa_entrada.grid(row=3, column=1)

alfa_2_entrada = Entry(variables_frame)
alfa_2_entrada.grid(row=4, column=1)
alfa_3_entrada = Entry(variables_frame)
alfa_3_entrada.grid(row=5, column=1)
alfa_4_entrada = Entry(variables_frame)
alfa_4_entrada.grid(row=6, column=1)
alfa_5_entrada = Entry(variables_frame)
alfa_5_entrada.grid(row=7, column=1)
alfa_6_entrada = Entry(variables_frame)
alfa_6_entrada.grid(row=8, column=1)

calcular_boton = Button(variables_frame, text="Calcular", command=calcular).grid(row=0, column=2, padx=30)

# Treeview Paredes

wind.tree = ttk.Treeview(height=6, columns=('#1', '#2', "#3"))
wind.tree.grid(row=1, column=0, columnspan=2)
wind.tree.heading("#1", text="Pared", anchor=CENTER)
wind.tree.heading("#2", text="Superficie", anchor=CENTER)
wind.tree.heading("#3", text="Coeficiente de absorción", anchor=CENTER)
wind.tree['show'] = 'headings'

# Treeview Resultados ----------------------------------------------------

frame_resultados = Frame(wind)
frame_resultados.grid(row=1, column=0, columnspan=2)

# Frame A

frame_2_a = Frame(frame_resultados)
frame_2_a.grid(row=0, column=0)

frame_2_a.tree = ttk.Treeview(height=6, columns=('#1', '#2'))
frame_2_a.tree.grid()
frame_2_a.tree.heading("#1", text="Criterio", anchor=CENTER)
frame_2_a.tree.heading("#2", text="Valor", anchor=CENTER)
frame_2_a.tree['show'] = 'headings'

# Frame B

frame_2_b = Frame(frame_resultados)
frame_2_b.grid(row=0, column=1)

frame_2_b.tree = ttk.Treeview(height=6, columns=('#1', '#2'))
frame_2_b.tree.grid()
frame_2_b.tree.heading("#1", text="Banda", anchor=CENTER)
frame_2_b.tree.heading("#2", text="Cantidad de modos", anchor=CENTER)
frame_2_b.tree['show'] = 'headings'
# ------------------------------------------------------------------------
# Treeview Modos de Resonancia

frame_3 = Frame(wind)
frame_3.grid(row=3, column=0, columnspan=2)

frame_3.tree = ttk.Treeview(height=6, columns=('#1', '#2', "#3"))
frame_3.tree.grid()
frame_3.tree.heading("#1", text="Combinación", anchor=CENTER)
frame_3.tree.heading("#2", text="Frecuencia del modo", anchor=CENTER)
frame_3.tree.heading("#3", text="Tipo de modo", anchor=CENTER)
frame_3.tree['show'] = 'headings'

"""fondorojo = Canvas(wind, bg="brown")
Canvas.create_line(fondorojo, 0, 3.5, 550, 90, width=3.5, fill="blue")
fondorojo.pack(padx=5, pady=3)"""

wind.mainloop()

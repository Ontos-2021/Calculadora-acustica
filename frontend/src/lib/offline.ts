import type { CalculateRequest, CalculateResponse } from "./types";

const PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

let pyodidePromise: Promise<unknown> | null = null;

async function getPyodide() {
  if (!pyodidePromise) {
    pyodidePromise = (async () => {
      const { loadPyodide } = await import(
        /* @vite-ignore */ `${PYODIDE_CDN}pyodide.js`
      );
      const py = await loadPyodide({ indexURL: PYODIDE_CDN });
      return py;
    })();
  }
  return pyodidePromise;
}

export async function isOnline(): Promise<boolean> {
  return navigator.onLine;
}

export async function calculateOffline(
  request: CalculateRequest,
): Promise<CalculateResponse> {
  const py = await getPyodide();
  const json = JSON.stringify(request);

  const result = await (
    py as unknown as { runPython: (code: string) => string }
  ).runPython(`
import json, math, sys

# --- acoustic_core inline ---
# (minified core logic for offline use)

BANDAS_OCTAVA = ["125", "250", "500", "1000", "2000", "4000"]
NOMBRES_SUP = ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"]
MATERIALES = {
    "Concreto": {"125": 0.01, "250": 0.02, "500": 0.04, "1000": 0.06, "2000": 0.08, "4000": 0.10},
    "Madera": {"125": 0.04, "250": 0.04, "500": 0.07, "1000": 0.06, "2000": 0.06, "4000": 0.07},
    "Yeso": {"125": 0.10, "250": 0.08, "500": 0.05, "1000": 0.04, "2000": 0.04, "4000": 0.05},
    "Vidrio": {"125": 0.03, "250": 0.03, "500": 0.05, "1000": 0.08, "2000": 0.10, "4000": 0.10},
    "Alfombra gruesa": {"125": 0.08, "250": 0.24, "500": 0.57, "1000": 0.69, "2000": 0.71, "4000": 0.73},
    "Cortina pesada": {"125": 0.10, "250": 0.30, "500": 0.50, "1000": 0.65, "2000": 0.70, "4000": 0.70},
    "Panel acústico": {"125": 0.20, "250": 0.60, "500": 0.85, "1000": 0.90, "2000": 0.85, "4000": 0.80},
    "Espuma acústica": {"125": 0.10, "250": 0.25, "500": 0.55, "1000": 0.70, "2000": 0.75, "4000": 0.70},
}
PROPORCIONES = {
    "Golden Ratio": (1, 1.25, 1.60),
    "Louden (1971)": (1, 1.14, 1.39),
    "Sepmeyer": (1, 1.19, 1.46),
    "Bonello": (1, 1.28, 1.54),
    "Volkmann": (1, 1.26, 1.59),
}
RT60_OBJETIVOS = {
    "home_studio": {"label": "Home Studio / Grabación", "valores": {"125": 0.30, "250": 0.30, "500": 0.30, "1000": 0.30, "2000": 0.30, "4000": 0.30}},
    "sala_conferencias": {"label": "Sala de conferencias", "valores": {"125": 0.70, "250": 0.70, "500": 0.70, "1000": 0.70, "2000": 0.70, "4000": 0.70}},
    "aula": {"label": "Aula", "valores": {"125": 0.75, "250": 0.75, "500": 0.80, "1000": 0.80, "2000": 0.80, "4000": 0.75}},
    "teatro": {"label": "Teatro", "valores": {"125": 1.00, "250": 1.00, "500": 1.00, "1000": 1.00, "2000": 1.00, "4000": 0.90}},
    "sala_conciertos": {"label": "Sala de conciertos", "valores": {"125": 1.80, "250": 1.80, "500": 1.80, "1000": 1.80, "2000": 1.60, "4000": 1.40}},
    "iglesia": {"label": "Iglesia / Culto", "valores": {"125": 2.20, "250": 2.20, "500": 2.20, "1000": 2.20, "2000": 2.00, "4000": 1.80}},
    "home_theater": {"label": "Home Theater", "valores": {"125": 0.40, "250": 0.40, "500": 0.40, "1000": 0.40, "2000": 0.40, "4000": 0.40}},
    "restaurante": {"label": "Restaurante", "valores": {"125": 0.50, "250": 0.50, "500": 0.60, "1000": 0.60, "2000": 0.60, "4000": 0.50}},
}

data = json.loads('${json}')
largo, ancho, alto = data["largo"], data["ancho"], data["alto"]
uso = data.get("uso")
volumen = largo * ancho * alto

areas = [ancho * alto, ancho * alto, largo * alto, largo * alto, largo * ancho, largo * ancho]
sup_areas = areas

def get_alpha(mat_name, banda):
    if mat_name in MATERIALES:
        return MATERIALES[mat_name].get(banda, 0.1)
    return 0.1

superficies = []
for i in range(6):
    sd = data["superficies"][i] if i < len(data["superficies"]) else {"material": "Concreto"}
    mat = sd.get("material", "Concreto")
    custom = sd.get("alphas", {})
    if custom:
        superficie = {"area": sup_areas[i], "nombre": NOMBRES_SUP[i], "alphas": custom}
    else:
        superficie = {"area": sup_areas[i], "nombre": NOMBRES_SUP[i], "alphas": MATERIALES.get(mat, {"125": 0.1})}
    superficies.append(superficie)

# Resonance modes
from itertools import product
modos = []
combinaciones = list(product(range(5), repeat=3))
combinaciones.remove((0, 0, 0))

for nx, ny, nz in combinaciones:
    x = (nx / largo) ** 2
    y = (ny / ancho) ** 2
    z = (nz / alto) ** 2
    f = round((343 / 2) * math.sqrt(x + y + z), 1)
    non_zero = sum(1 for n in (nx, ny, nz) if n > 0)
    if non_zero == 1:
        tipo, peso = "axial", 0.0
    elif non_zero == 2:
        tipo, peso = "tangencial", -3.0
    else:
        tipo, peso = "oblicuo", -6.0
    modos.append({"indices": [nx, ny, nz], "frecuencia": f, "tipo": tipo, "peso_db": peso, "degenerado": False, "solapado": False})

modos.sort(key=lambda m: m["frecuencia"])

# RT60
def calc_rt60_banda(banda):
    A = sum(s["area"] * s["alphas"].get(banda, 0) for s in superficies)
    if A <= 0: return {"Sabine": 0, "Eyring": 0, "Millington": 0, "FitzRoy": 0}
    S_total = sum(s["area"] for s in superficies)
    sab = 0.161 * volumen / A
    alpha_prom = A / S_total
    eyr = (0.161 * volumen) / (-S_total * math.log(max(1 - alpha_prom, 1e-10))) if alpha_prom < 1 else 0
    mill_A = sum(-s["area"] * math.log(max(1 - s["alphas"].get(banda, 0), 1e-10)) for s in superficies)
    mill = 0.161 * volumen / mill_A if mill_A > 0 else 0
    sx = superficies[0]["area"] + superficies[1]["area"]
    sy = superficies[2]["area"] + superficies[3]["area"]
    sz = superficies[4]["area"] + superficies[5]["area"]
    ax = (superficies[0]["alphas"].get(banda, 0) + superficies[1]["alphas"].get(banda, 0)) / 2
    ay = (superficies[2]["alphas"].get(banda, 0) + superficies[3]["alphas"].get(banda, 0)) / 2
    az = (superficies[4]["alphas"].get(banda, 0) + superficies[5]["alphas"].get(banda, 0)) / 2
    fr = (0.161 * volumen * (sx / -math.log(max(1-ax,1e-10)) + sy / -math.log(max(1-ay,1e-10)) + sz / -math.log(max(1-az,1e-10)))) / (S_total ** 2) if S_total > 0 and ax < 1 and ay < 1 and az < 1 else 0
    return {"Sabine": round(sab, 2), "Eyring": round(eyr, 2), "Millington": round(mill, 2), "FitzRoy": round(fr, 2)}

rt60_bandas = {b: calc_rt60_banda(b) for b in BANDAS_OCTAVA}

# RT60 promedio
A_total = sum(s["area"] * sum(s["alphas"].values()) / len(s["alphas"]) for s in superficies)
rt60_prom = round(0.161 * volumen / A_total, 2) if A_total > 0 else 0

# Schroeder
f_sch = round(2000 * math.sqrt(max(rt60_prom, 0.01) / max(volumen, 0.01)), 1) if rt60_prom > 0 and volumen > 0 else 0

# Modal bandwidth
delta_f = round(2.2 / max(rt60_prom, 0.01), 2) if rt60_prom > 0 else 0

# Degenerate + overlapping
freq_map = {}
for i, m in enumerate(modos):
    freq_map.setdefault(m["frecuencia"], []).append(i)
for idxs in freq_map.values():
    if len(idxs) > 1:
        for i in idxs:
            modos[i]["degenerado"] = True
for i in range(len(modos) - 1):
    if abs(modos[i+1]["frecuencia"] - modos[i]["frecuencia"]) < delta_f:
        modos[i]["solapado"] = True
        modos[i+1]["solapado"] = True

frecuencias = [m["frecuencia"] for m in modos]

# Bonello
n = 125
bandas_bon = {}
for banda_idx in range(-8, 23):
    bandas_bon[n * (2 ** (banda_idx / 3))] = []
for freq in frecuencias:
    for central in sorted(bandas_bon.keys()):
        if freq < central:
            bandas_bon[central].append(freq)
            break
bonello_result = {}
for freq_c, modos_list in sorted(bandas_bon.items()):
    if freq_c < 500 or len(modos_list) != 0:
        bonello_result[round(freq_c, 1)] = len(modos_list)
counts = list(bonello_result.values())
violaciones = [i for i in range(1, len(counts)) if counts[i] < counts[i-1]]
bonello = {"cumple": len(violaciones) == 0, "bandas": bonello_result, "violaciones": violaciones, "total_modos": sum(counts)}

# Distribution
dist = {"axiales": sum(1 for m in modos if m["tipo"] == "axial"), "tangenciales": sum(1 for m in modos if m["tipo"] == "tangencial"), "oblicuos": sum(1 for m in modos if m["tipo"] == "oblicuo"), "degenerados": sum(1 for m in modos if m["degenerado"]), "solapados": sum(1 for m in modos if m["solapado"])}

# Proportions
dims = sorted([largo, ancho, alto])
prop_actual = (1, round(dims[1]/dims[0], 2), round(dims[2]/dims[0], 2))
mejores = []
for nombre, (r1, r2, r3) in PROPORCIONES.items():
    error = abs(prop_actual[1] - r2) + abs(prop_actual[2] - r3)
    mejores.append((error, nombre, r2, r3))
mejores.sort()
proporciones = {"proporcion_actual": prop_actual, "mas_cercana": mejores[0][1], "proporcion_cercana": (1, mejores[0][2], mejores[0][3]), "error": round(mejores[0][0], 3), "todas": [(n, r2, r3) for _, n, r2, r3 in mejores]}

# Degenerate dimensions
deg_dims = []
dim_pairs = [("Largo", largo), ("Ancho", ancho), ("Alto", alto)]
for i in range(len(dim_pairs)):
    for j in range(i+1, len(dim_pairs)):
        n1, v1 = dim_pairs[i]
        n2, v2 = dim_pairs[j]
        if abs(v1 - v2) < 0.01:
            deg_dims.append(f"{n1} = {n2} ({v1:.2f}m): dimensiones iguales -> alta degeneración modal")
        elif v1 > v2 and abs(v1 / v2 - round(v1 / v2)) < 0.01:
            ratio = round(v1 / v2)
            deg_dims.append(f"{n1} es múltiplo de {n2} ({ratio}x): puede causar modos degenerados")

# Objetivo
objetivo = None
if uso and uso in RT60_OBJETIVOS:
    objetivo = RT60_OBJETIVOS[uso]
    objetivo["diferencias"] = {}
    for banda in BANDAS_OCTAVA:
        sab = rt60_bandas[banda]["Sabine"]
        tgt = objetivo["valores"].get(banda, 0)
        objetivo["diferencias"][banda] = round(abs(sab - tgt), 2)

json.dumps({
    "modos": modos,
    "frecuencias": frecuencias,
    "cantidad_modos": len(modos),
    "distribucion": dist,
    "rt60_bandas": rt60_bandas,
    "rt60_promedio": rt60_prom,
    "f_schroeder": f_sch,
    "delta_f": delta_f,
    "bonello": bonello,
    "proporciones": proporciones,
    "degeneracion_dimensiones": deg_dims,
    "objetivo": objetivo,
})
  `);

  return JSON.parse(result);
}

import type { CalculateRequest, CalculateResponse } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PYODIDE_CDN = "https://cdn.jsdelivr.net/pyodide/v0.26.4/full/";

let pyodidePromise: Promise<unknown> | null = null;
let coreBundleCache: Record<string, string> | null = null;

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

async function getCoreBundle(): Promise<Record<string, string>> {
  if (!coreBundleCache) {
    const res = await fetch(`${API_BASE}/api/v1/core-bundle`);
    if (res.ok) coreBundleCache = await res.json();
    else throw new Error("No se pudo cargar el core acústico");
  }
  return coreBundleCache!;
}

function stripPydanticFromSource(src: string): string {
  return src
    .replace(/from\s+pydantic\s+import\s+.*/g, "")
    .replace(/from\s+typing\s+import\s+Optional/g, "")
    .replace(/@model_validator\(.*\)\s*\n/g, "")
    .replace(/BaseModel/g, "object")
    .replace(/Field\([^)]*\)/g, "None")
    .replace(/Optional\[([^\]]+)\]/g, "$1 | None")
    .replace(/\s+def validar_alphas.*?:$/, "  def validar_alphas(self): pass");
}

async function loadCoreInPyodide(py: unknown): Promise<boolean> {
  const p = py as any;
  try {
    await p.loadPackage("pydantic");
  } catch {
    return false;
  }
  try {
    const bundle = await getCoreBundle();
    for (const [fname, code] of Object.entries(bundle)) {
      const sanitized = code.replace(/from\s+\.models\s+import/, "from acoustic_core.models import");
      p.runPython(sanitized, { filename: `/acoustic_core/${fname}` });
    }
    p.runPython("from acoustic_core import *");
    return true;
  } catch {
    return false;
  }
}

export async function isOnline(): Promise<boolean> {
  return navigator.onLine;
}

const INLINE_CODE = `
import json, math, sys, cmath
from itertools import product

BANDAS_OCTAVA = ["125","250","500","1000","2000","4000"]
C = 343.0

def classify_iso11654(alphas):
    vals = [alphas.get(b,0) for b in ["250","500","1000","2000"]]
    aw = min(round(sum(vals)/len(vals)/0.05)*0.05, 1.0)
    cls = "A" if aw>=0.9 else "B" if aw>=0.8 else "C" if aw>=0.6 else "D" if aw>=0.3 else "E" if aw>=0.15 else "No clasificado"
    return aw, cls

MATERIALES = {
` +
`  "Concreto": {"125":0.01,"250":0.02,"500":0.04,"1000":0.06,"2000":0.08,"4000":0.10},
  "Madera": {"125":0.04,"250":0.04,"500":0.07,"1000":0.06,"2000":0.06,"4000":0.07},
  "Yeso": {"125":0.10,"250":0.08,"500":0.05,"1000":0.04,"2000":0.04,"4000":0.05},
  "Vidrio": {"125":0.03,"250":0.03,"500":0.05,"1000":0.08,"2000":0.10,"4000":0.10},
  "Alfombra gruesa": {"125":0.08,"250":0.24,"500":0.57,"1000":0.69,"2000":0.71,"4000":0.73},
  "Cortina pesada": {"125":0.10,"250":0.30,"500":0.50,"1000":0.65,"2000":0.70,"4000":0.70},
  "Panel acústico": {"125":0.20,"250":0.60,"500":0.85,"1000":0.90,"2000":0.85,"4000":0.80},
  "Espuma acústica": {"125":0.10,"250":0.25,"500":0.55,"1000":0.70,"2000":0.75,"4000":0.70},
  "Concreto sin pintar": {"125":0.01,"250":0.02,"500":0.04,"1000":0.06,"2000":0.08,"4000":0.10},
  "Panel fibra de vidrio (50mm)": {"125":0.20,"250":0.60,"500":0.85,"1000":0.90,"2000":0.85,"4000":0.80},
  "Lana mineral (100mm)": {"125":0.35,"250":0.75,"500":0.90,"1000":0.95,"2000":0.90,"4000":0.85},
  "Alfombra gruesa sobre espuma": {"125":0.08,"250":0.24,"500":0.57,"1000":0.69,"2000":0.71,"4000":0.73},
  "Cortina pesada (terciopelo)": {"125":0.10,"250":0.30,"500":0.50,"1000":0.65,"2000":0.70,"4000":0.70},
  "Espuma de poliuretano (50mm)": {"125":0.15,"250":0.35,"500":0.65,"1000":0.80,"2000":0.80,"4000":0.75},
  "Madera contrachapada (10mm)": {"125":0.05,"250":0.05,"500":0.07,"1000":0.06,"2000":0.06,"4000":0.07},
  "Escayola lisa": {"125":0.04,"250":0.04,"500":0.05,"1000":0.06,"2000":0.08,"4000":0.08},
  "Vidrio simple (3-6mm)": {"125":0.03,"250":0.03,"500":0.05,"1000":0.08,"2000":0.10,"4000":0.10},
}
` +
`
PROPORCIONES = {"Golden Ratio":(1,1.25,1.60),"Louden (1971)":(1,1.14,1.39),"Sepmeyer":(1,1.19,1.46),"Bonello":(1,1.28,1.54),"Volkmann":(1,1.26,1.59)}
RT60_OBJETIVOS = {"home_studio":{"label":"Home Studio / Grabaci\\u00f3n","valores":{"125":0.30,"250":0.30,"500":0.30,"1000":0.30,"2000":0.30,"4000":0.30}},"sala_conferencias":{"label":"Sala de conferencias","valores":{"125":0.70,"250":0.70,"500":0.70,"1000":0.70,"2000":0.70,"4000":0.70}},"aula":{"label":"Aula","valores":{"125":0.75,"250":0.75,"500":0.80,"1000":0.80,"2000":0.80,"4000":0.75}},"teatro":{"label":"Teatro","valores":{"125":1.00,"250":1.00,"500":1.00,"1000":1.00,"2000":1.00,"4000":0.90}},"sala_conciertos":{"label":"Sala de conciertos","valores":{"125":1.80,"250":1.80,"500":1.80,"1000":1.80,"2000":1.60,"4000":1.40}},"home_theater":{"label":"Home Theater","valores":{"125":0.40,"250":0.40,"500":0.40,"1000":0.40,"2000":0.40,"4000":0.40}}}

data = json.loads('$JSON')
largo, ancho, alto = data["largo"], data["ancho"], data["alto"]
uso = data.get("uso")
volumen = largo * ancho * alto
areas = [ancho*alto, ancho*alto, largo*alto, largo*alto, largo*ancho, largo*ancho]
SUP_NOMBRES = ["Frente","Contrafrente","Lat Izq","Lat Der","Piso","Techo"]

def get_alpha(mat_name, banda):
    if mat_name in MATERIALES:
        return MATERIALES[mat_name].get(banda, 0.1)
    return 0.1

superficies = []
for i in range(6):
    sd = data["superficies"][i] if i < len(data["superficies"]) else {"material":"Concreto"}
    mat = sd.get("material","Concreto")
    custom = sd.get("alphas",{})
    if custom:
        superficie = {"area": areas[i], "nombre": SUP_NOMBRES[i], "alphas": custom}
    else:
        superficie = {"area": areas[i], "nombre": SUP_NOMBRES[i], "alphas": MATERIALES.get(mat, {"125":0.1})}
    superficies.append(superficie)

modos = []
for nx, ny, nz in product(range(5), repeat=3):
    if nx==0 and ny==0 and nz==0: continue
    f = round((343/2)*math.sqrt((nx/largo)**2+(ny/ancho)**2+(nz/alto)**2), 1)
    nz_count = sum(1 for n in (nx,ny,nz) if n>0)
    tipo = ["oblicuo","axial","tangencial","oblicuo"][nz_count] if nz_count<=3 else "oblicuo"
    peso = [0,-3,-6][nz_count-1] if nz_count<=3 else -6
    modos.append({"indices":[nx,ny,nz],"frecuencia":f,"tipo":tipo,"peso_db":peso,"degenerado":False,"solapado":False})
modos.sort(key=lambda m:m["frecuencia"])

def calc_rt60_banda(banda):
    A = sum(s["area"]*s["alphas"].get(banda,0) for s in superficies)
    if A<=0: return {"Sabine":0,"Eyring":0,"Millington":0,"FitzRoy":0}
    S_total = sum(s["area"] for s in superficies)
    sab = 0.161*volumen/A
    alpha_prom = A/S_total
    eyr = (0.161*volumen)/(-S_total*math.log(max(1-alpha_prom,1e-10))) if alpha_prom<1 else 0
    mill_A = sum(-s["area"]*math.log(max(1-s["alphas"].get(banda,0),1e-10)) for s in superficies)
    mill = 0.161*volumen/mill_A if mill_A>0 else 0
    sx=superficies[0]["area"]+superficies[1]["area"]
    sy=superficies[2]["area"]+superficies[3]["area"]
    sz=superficies[4]["area"]+superficies[5]["area"]
    ax=(superficies[0]["alphas"].get(banda,0)+superficies[1]["alphas"].get(banda,0))/2
    ay=(superficies[2]["alphas"].get(banda,0)+superficies[3]["alphas"].get(banda,0))/2
    az=(superficies[4]["alphas"].get(banda,0)+superficies[5]["alphas"].get(banda,0))/2
    fr = (0.161*volumen*(sx/(-math.log(max(1-ax,1e-10)))+sy/(-math.log(max(1-ay,1e-10)))+sz/(-math.log(max(1-az,1e-10)))))/(S_total**2) if S_total>0 and ax<1 and ay<1 and az<1 else 0
    return {"Sabine":round(sab,2),"Eyring":round(eyr,2),"Millington":round(mill,2),"FitzRoy":round(fr,2)}

rt60_bandas = {b:calc_rt60_banda(b) for b in BANDAS_OCTAVA}
A_total = sum(s["area"]*sum(s["alphas"].values())/len(s["alphas"]) for s in superficies)
rt60_prom = round(0.161*volumen/A_total,2) if A_total>0 else 0
f_sch = round(2000*math.sqrt(max(rt60_prom,0.01)/max(volumen,0.01)),1) if rt60_prom>0 and volumen>0 else 0
delta_f = round(2.2/max(rt60_prom,0.01),2) if rt60_prom>0 else 0
freq_map = {}
for i,m in enumerate(modos):
    freq_map.setdefault(m["frecuencia"],[]).append(i)
for idxs in freq_map.values():
    if len(idxs)>1:
        for i in idxs: modos[i]["degenerado"] = True
for i in range(len(modos)-1):
    if abs(modos[i+1]["frecuencia"]-modos[i]["frecuencia"])<delta_f:
        modos[i]["solapado"] = modos[i+1]["solapado"] = True
frecuencias = [m["frecuencia"] for m in modos]

n=125; bandas_bon={}
for bi in range(-8,23): bandas_bon[n*(2**(bi/3))]=[]
for freq in frecuencias:
    for central in sorted(bandas_bon.keys()):
        if freq<central: bandas_bon[central].append(freq); break
bonello_r={}
for fc,ml in sorted(bandas_bon.items()):
    if fc<500 or len(ml)!=0: bonello_r[round(fc,1)]=len(ml)
counts=list(bonello_r.values())
violaciones=[i for i in range(1,len(counts)) if counts[i]<counts[i-1]]
bonello={"cumple":len(violaciones)==0,"bandas":bonello_r,"violaciones":violaciones,"total_modos":sum(counts)}
dist={"axiales":sum(1 for m in modos if m["tipo"]=="axial"),"tangenciales":sum(1 for m in modos if m["tipo"]=="tangencial"),"oblicuos":sum(1 for m in modos if m["tipo"]=="oblicuo"),"degenerados":sum(1 for m in modos if m["degenerado"]),"solapados":sum(1 for m in modos if m["solapado"])}
dims=sorted([largo,ancho,alto])
prop_actual=(1,round(dims[1]/dims[0],2),round(dims[2]/dims[0],2))
mejores=sorted([(abs(prop_actual[1]-r2)+abs(prop_actual[2]-r3),n,r2,r3) for n,(r1,r2,r3) in PROPORCIONES.items()])
proporciones={"proporcion_actual":prop_actual,"mas_cercana":mejores[0][1],"proporcion_cercana":(1,mejores[0][2],mejores[0][3]),"error":round(mejores[0][0],3),"todas":[(n,r2,r3) for _,n,r2,r3 in mejores]}
deg_dims=[]
dim_pairs=[("Largo",largo),("Ancho",ancho),("Alto",alto)]
for i in range(len(dim_pairs)):
    for j in range(i+1,len(dim_pairs)):
        n1,v1=dim_pairs[i]; n2,v2=dim_pairs[j]
        if abs(v1-v2)<0.01:
            deg_dims.append(f"{n1} = {n2} ({v1:.2f}m): dimensiones iguales -> alta degeneraci\\u00f3n modal")
        elif v1>v2 and abs(v1/v2-round(v1/v2))<0.01:
            deg_dims.append(f"{n1} es m\\u00faltiplo de {n2} ({round(v1/v2)}x): puede causar modos degenerados")
objetivo=None
if uso and uso in RT60_OBJETIVOS:
    objetivo=RT60_OBJETIVOS[uso]
    objetivo["diferencias"]={}
    for banda in BANDAS_OCTAVA:
        objetivo["diferencias"][banda]=round(abs(rt60_bandas[banda]["Sabine"]-objetivo["valores"].get(banda,0)),2)

json.dumps({"modos":modos,"frecuencias":frecuencias,"cantidad_modos":len(modos),"distribucion":dist,"rt60_bandas":rt60_bandas,"rt60_promedio":rt60_prom,"f_schroeder":f_sch,"delta_f":delta_f,"bonello":bonello,"proporciones":proporciones,"degeneracion_dimensiones":deg_dims,"objetivo":objetivo})
`;

export async function calculateOffline(
  request: CalculateRequest,
): Promise<CalculateResponse> {
  const json = JSON.stringify(request);

  try {
    const py = await getPyodide();
    const loaded = await loadCoreInPyodide(py);
    if (loaded) {
      const result = await (py as any).runPython(`
import json, math
${json}
`);
      return JSON.parse(result);
    }
  } catch {
    // fall through to inline
  }

  const py = await getPyodide();
  const result = await (py as any).runPython(
    INLINE_CODE.replace("$JSON", json)
  );
  return JSON.parse(result);
}

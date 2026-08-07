from fastapi import APIRouter, HTTPException

from acoustic_core.models import Room, Surface, Material, BANDAS_OCTAVA
from acoustic_core.resonance import calculate_modes, detect_degenerate_modes, detect_overlapping_modes
from acoustic_core.reverberation import calculate_rt60, rt60_promedio_sabine
from acoustic_core.evaluation import (
    calculate_schroeder, calculate_modal_bandwidth,
    evaluate_bonello, find_degenerate_dimensions, get_mode_distribution,
)
from acoustic_core.design import find_closest_ratio, get_rt60_target
from acoustic_core.presets import MATERIALES_PRESETS
from .schemas import CalculateRequest, CalculateResponse, HealthResponse

router = APIRouter()

NOMBRES_SUPERFICIES = ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"]
SUPERFICIE_AREAS = [
    lambda l, a, h: a * h,
    lambda l, a, h: a * h,
    lambda l, a, h: l * h,
    lambda l, a, h: l * h,
    lambda l, a, h: l * a,
    lambda l, a, h: l * a,
]


def _build_room(req: CalculateRequest) -> Room:
    superficies = []
    for i in range(6):
        nombre = NOMBRES_SUPERFICIES[i]
        area = SUPERFICIE_AREAS[i](req.largo, req.ancho, req.alto)
        sd = req.superficies[i]
        mat_nombre = sd.material
        base = MATERIALES_PRESETS.get(mat_nombre, Material(nombre=mat_nombre, alpha_unico=0.1))
        if sd.alphas:
            material = Material(nombre=mat_nombre, alphas=sd.alphas)
        else:
            material = base
        superficies.append(Surface(nombre=nombre, area=area, material=material))
    return Room(largo=req.largo, ancho=req.ancho, alto=req.alto, superficies=superficies, uso=req.uso)


def _compute_all(room: Room) -> dict:
    modos = calculate_modes(room)
    rt60_bandas = calculate_rt60(room)
    rt60_prom = rt60_promedio_sabine(room)
    delta_f = calculate_modal_bandwidth(rt60_prom)
    modos = detect_degenerate_modes(modos)
    modos = detect_overlapping_modes(modos, delta_f)
    frecuencias = [m.frecuencia for m in modos]
    bonello = evaluate_bonello(frecuencias)
    f_schroeder = calculate_schroeder(rt60_prom, room.volumen)
    distribucion = get_mode_distribution(modos)
    proporciones = find_closest_ratio(room.largo, room.ancho, room.alto)
    degeneracion_dims = find_degenerate_dimensions(room.largo, room.ancho, room.alto)
    objetivo = get_rt60_target(room.uso) if room.uso else None
    if objetivo:
        for banda in BANDAS_OCTAVA:
            sabine = rt60_bandas[banda]["Sabine"]
            target = objetivo["valores"].get(banda, 0)
            objetivo.setdefault("diferencias", {})[banda] = round(abs(sabine - target), 2)
    return {
        "modos": [m.model_dump(mode='json') for m in modos],
        "frecuencias": frecuencias,
        "cantidad_modos": len(modos),
        "distribucion": distribucion,
        "rt60_bandas": rt60_bandas,
        "rt60_promedio": rt60_prom,
        "f_schroeder": f_schroeder,
        "delta_f": delta_f,
        "bonello": bonello,
        "proporciones": proporciones,
        "degeneracion_dimensiones": degeneracion_dims,
        "objetivo": objetivo,
    }


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/calculate", response_model=CalculateResponse)
async def calculate(data: CalculateRequest):
    room = _build_room(data)
    datos = _compute_all(room)
    return CalculateResponse(**datos)


@router.get("/materials")
async def list_materials():
    result = {}
    for name, mat in MATERIALES_PRESETS.items():
        result[name] = {"alphas": mat.alphas, "label": name}
    return result


@router.get("/design/ratios")
async def design_ratios():
    from acoustic_core.design import PROPORCIONES
    return {k: v for k, v in PROPORCIONES.items()}


@router.get("/design/targets")
async def design_targets():
    from acoustic_core.design import RT60_OBJETIVOS
    return RT60_OBJETIVOS

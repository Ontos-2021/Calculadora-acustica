from fastapi import APIRouter, HTTPException, Depends, Security, Query
from .dependencies import verify_endpoint_access, check_feature

from acoustic_core.models import Room, Surface, Material, BANDAS_OCTAVA
from acoustic_core.resonance import calculate_modes, detect_degenerate_modes, detect_overlapping_modes
from acoustic_core.reverberation import calculate_rt60, rt60_promedio_sabine
from acoustic_core.evaluation import (
    calculate_schroeder, calculate_modal_bandwidth,
    evaluate_bonello, find_degenerate_dimensions, get_mode_distribution,
)
from acoustic_core.design import find_closest_ratio, get_rt60_target
from acoustic_core.presets import MATERIALES_PRESETS, CATEGORIAS, search_materials, calculate_air_absorption, AIR_ABSORPTION_DEFAULT, AudienceConfig, calculate_audience_absorption
from acoustic_core.pressure import compute_pressure_map, compute_single_mode_grid, find_optimal_listening
from acoustic_core.impulse import generate_image_sources, calculate_energy, build_impulse_response, calculate_iso3382_parameters
from .schemas import (
    CalculateRequest, CalculateResponse, HealthResponse,
    PressureMapRequest, PressureMapResponse, IRRequest, IRResponse,
    MaterialResponse, MaterialSearchRequest,
    AirAbsorptionRequest, AirAbsorptionResponse,
    AudienceAbsorptionRequest,
)

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


def _material_to_response(mat: Material) -> MaterialResponse:
    return MaterialResponse(
        nombre=mat.nombre,
        categoria=mat.categoria,
        alphas=mat.alphas,
        alpha_w=mat.alpha_w,
        iso_class=mat.iso_class,
    )


@router.get("/materials")
async def list_materials(
    categoria: str = Query(default=""),
    min_alpha_w: float = Query(default=0.0, ge=0, le=1),
    max_alpha_w: float = Query(default=1.0, ge=0, le=1),
    iso_class: str = Query(default=""),
    query: str = Query(default=""),
):
    if query or categoria or min_alpha_w > 0 or max_alpha_w < 1 or iso_class:
        results = search_materials(query, categoria, min_alpha_w, max_alpha_w, iso_class)
        return [_material_to_response(m) for m in results]
    return [_material_to_response(m) for m in MATERIALES_PRESETS.values()]


@router.get("/materials/categories")
async def material_categories():
    return CATEGORIAS


@router.get("/materials/{name}")
async def material_detail(name: str):
    mat = MATERIALES_PRESETS.get(name)
    if not mat:
        raise HTTPException(404, f"Material '{name}' no encontrado")
    return _material_to_response(mat)


@router.get("/design/ratios")
async def design_ratios():
    from acoustic_core.design import PROPORCIONES
    return {k: v for k, v in PROPORCIONES.items()}


@router.get("/design/targets")
async def design_targets():
    from acoustic_core.design import RT60_OBJETIVOS
    return RT60_OBJETIVOS


@router.post("/design/air-absorption", response_model=AirAbsorptionResponse)
async def air_absorption(data: AirAbsorptionRequest):
    coeficientes = {}
    for b in BANDAS_OCTAVA:
        coeficientes[b] = round(calculate_air_absorption(float(b), data.humidity, data.temp_celsius), 8)
    return AirAbsorptionResponse(
        coeficientes=coeficientes,
        humidity=data.humidity,
        temp_celsius=data.temp_celsius,
    )


@router.post("/design/audience-absorption")
async def audience_absorption(data: AudienceAbsorptionRequest):
    config = AudienceConfig(
        num_people=data.num_people,
        seated=data.seated,
        upholstered=data.upholstered,
        occupied=data.occupied,
    )
    return calculate_audience_absorption(config)


@router.post("/pressure-map", response_model=PressureMapResponse)
async def pressure_map(data: PressureMapRequest):
    room = _build_room(CalculateRequest(
        largo=data.largo, ancho=data.ancho, alto=data.alto,
        superficies=data.superficies,
    ))
    modos = calculate_modes(room)

    if data.mode_indices and len(data.mode_indices) == 3:
        result = compute_single_mode_grid(
            room, *data.mode_indices,
            ear_height=data.ear_height, grid_size=data.grid_size,
        )
        max_freq_for_label = 0
        num_modos_for_label = 1
    else:
        result = compute_pressure_map(
            room, modos=modos,
            max_freq=data.max_freq,
            ear_height=data.ear_height,
            grid_size=data.grid_size,
        )
        max_freq_for_label = data.max_freq
        num_modos_for_label = result.get("num_modos", 0)

    optimal = find_optimal_listening(
        room, modos=modos,
        max_freq=data.max_freq,
        ear_height=data.ear_height,
    )

    return PressureMapResponse(
        grid_x=result["grid_x"],
        grid_y=result["grid_y"],
        pressure=result["pressure"],
        max_freq=max_freq_for_label,
        ear_height=data.ear_height,
        num_modos=num_modos_for_label,
        optimal_listening=optimal,
    )


@router.post("/impulse-response", response_model=IRResponse)
async def impulse_response(
    data: IRRequest,
    tier: dict = Depends(verify_endpoint_access),
):
    if not check_feature(tier, "/api/v1/impulse-response"):
        raise HTTPException(403, "Requiere licencia PAID (feature: ism)")
    room = _build_room(CalculateRequest(
        largo=data.largo, ancho=data.ancho, alto=data.alto,
        superficies=data.superficies,
    ))

    source = tuple(data.source)
    receiver = tuple(data.receiver)

    sources = generate_image_sources(room, source, receiver, max_order=data.max_order)
    sources = calculate_energy(sources, room, "500")

    ir_data = build_impulse_response(
        sources, fs=data.sample_rate,
        duration_s=1.0, room=room,
    )

    params = calculate_iso3382_parameters(
        ir_data["impulse_response"],
        data.sample_rate,
        ir_data["direct_delay_ms"],
    )

    return IRResponse(
        impulse_response=ir_data["impulse_response"],
        sample_rate=data.sample_rate,
        direct_delay_ms=ir_data["direct_delay_ms"],
        parameters=params,
    )

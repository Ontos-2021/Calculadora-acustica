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
from acoustic_core.inverse import required_absorption, current_absorption, missing_absorption, suggest_materials, suggest_placement
from acoustic_core.absorbers import porous_absorption, helmholtz_resonator, membrane_absorber
from acoustic_core.diffusers import qrd_well_depths, skyline_well_depths, estimate_diffusion_coefficient
from acoustic_core.isolation import single_panel_tl, double_panel_tl, calculate_stc, calculate_rw, evaluate_nc, get_nc_target, msr_resonance, critical_frequency
from acoustic_core.pressure import compute_pressure_map, compute_single_mode_grid, find_optimal_listening
from acoustic_core.impulse import generate_image_sources, calculate_energy, build_impulse_response, calculate_iso3382_parameters
from .schemas import (
    CalculateRequest, CalculateResponse, HealthResponse,
    PressureMapRequest, PressureMapResponse, IRRequest, IRResponse,
    MaterialResponse, MaterialSearchRequest,
    AirAbsorptionRequest, AirAbsorptionResponse,
    AudienceAbsorptionRequest,
    InverseDesignRequest, InverseDesignResponse,
    MaterialSuggestion, PlacementSuggestion,
    PorousAbsorberRequest, HelmholtzRequest, MembraneRequest, AbsorberResponse,
    QRDRequest, SkylineRequest,
    SinglePanelTLRequest, DoublePanelTLRequest, NCEvaluationRequest,
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


@router.post("/design/absorbers/porous", response_model=AbsorberResponse)
async def porous_absorber(data: PorousAbsorberRequest):
    alpha = porous_absorption(data.thickness_m, data.flow_resistivity, data.density_kgm3)
    return AbsorberResponse(f0=0, Q=0, alpha=alpha)


@router.post("/design/absorbers/helmholtz", response_model=AbsorberResponse)
async def helmholtz_absorber(data: HelmholtzRequest):
    result = helmholtz_resonator(data.neck_area_m2, data.cavity_volume_m3, data.neck_length_m, data.neck_radius_m)
    return AbsorberResponse(f0=result["f0"], Q=result["Q"], alpha=result["alpha"])


@router.post("/design/absorbers/membrane", response_model=AbsorberResponse)
async def membrane_absorber_endpoint(data: MembraneRequest):
    result = membrane_absorber(data.mass_per_area_kgm2, data.air_gap_m)
    return AbsorberResponse(f0=result["f0"], Q=result["Q"], alpha=result["alpha"])


@router.post("/design/diffusers/qrd")
async def qrd_calculator(data: QRDRequest):
    result = qrd_well_depths(data.design_freq_hz, data.prime_n, data.well_width_m)
    if "error" in result:
        raise HTTPException(400, result["error"])
    result["diffusion_coefficient"] = estimate_diffusion_coefficient(data.design_freq_hz, result["max_depth_m"])
    return result


@router.post("/design/diffusers/skyline")
async def skyline_calculator(data: SkylineRequest):
    result = skyline_well_depths(data.design_freq_hz, data.grid_n, data.well_size_m)
    if "error" in result:
        raise HTTPException(400, result["error"])
    return result


@router.post("/design/isolation/single-panel")
async def single_panel(data: SinglePanelTLRequest):
    from acoustic_core.isolation import MATERIAL_C_L
    c_l = data.c_l_material if data.c_l_material > 0 else MATERIAL_C_L.get(data.material_type, 3500)
    tl = single_panel_tl(data.mass_per_area_kgm2, data.thickness_m, data.material_type)
    fc = critical_frequency(data.thickness_m, c_l)
    stc = calculate_stc(tl)
    rw = calculate_rw(tl)
    return {
        "tl": tl,
        "fc_hz": fc,
        "mass_per_area_kgm2": data.mass_per_area_kgm2,
        "thickness_m": data.thickness_m,
        **stc,
        **rw,
    }


@router.post("/design/isolation/double-panel")
async def double_panel(data: DoublePanelTLRequest):
    tl = double_panel_tl(data.m1_kgm2, data.m2_kgm2, data.gap_m, data.stud_connection)
    f0 = msr_resonance(data.m1_kgm2, data.m2_kgm2, data.gap_m)
    return {
        "tl": tl,
        "f0_hz": f0,
        "m1_kgm2": data.m1_kgm2,
        "m2_kgm2": data.m2_kgm2,
        "gap_m": data.gap_m,
        "stud_connection": data.stud_connection,
    }


@router.post("/design/isolation/nc")
async def nc_evaluation(data: NCEvaluationRequest):
    result = evaluate_nc(data.spl)
    return result


@router.get("/design/isolation/nc-targets")
async def nc_targets():
    from acoustic_core.isolation import NC_TARGETS
    return NC_TARGETS


@router.post("/design/inverse", response_model=InverseDesignResponse)
async def inverse_design(data: InverseDesignRequest):
    room = _build_room(CalculateRequest(
        largo=data.largo, ancho=data.ancho, alto=data.alto,
        superficies=data.superficies, uso=data.target_uso,
    ))
    target = get_rt60_target(data.target_uso)
    if not target:
        raise HTTPException(400, f"Uso objetivo '{data.target_uso}' no válido")
    targets = target["valores"]

    req = required_absorption(room.volumen, targets)
    curr = current_absorption(room)
    miss = missing_absorption(room, targets)
    mats = suggest_materials(room, data.target_uso)

    placements = []
    if data.include_placement:
        from acoustic_core.resonance import calculate_modes
        from acoustic_core.pressure import compute_pressure_map
        modos = calculate_modes(room)
        pmap = compute_pressure_map(room, modos=modos, max_freq=300.0)
        placements = suggest_placement(room, data.target_uso, pmap)

    return InverseDesignResponse(
        current_absorption=curr,
        required_absorption=req,
        missing_absorption=miss,
        material_suggestions=[MaterialSuggestion(**m) for m in mats if "mensaje" not in m],
        placement_suggestions=[PlacementSuggestion(**p) for p in placements],
    )


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

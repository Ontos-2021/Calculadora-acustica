from __future__ import annotations

import cmath
import io
import math
import os
from collections.abc import Mapping
from urllib.parse import quote
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from acoustic_core.absorbers import (
    helmholtz_resonator,
    membrane_absorber,
    porous_absorber_estimate,
    recommended_absorber_area,
)
from acoustic_core.design import (
    DIMENSION_CONVENTION,
    PROPORCIONES,
    RT60_OBJETIVOS,
    evaluate_bolt_area,
    find_closest_ratio,
    get_rt60_target,
)
from acoustic_core.diffusers import (
    diffusion_coefficient_diagnostics,
    estimate_diffusion_coefficient,
    qrd_well_depths,
    simulate_qrd_polar_response,
    skyline_well_depths,
)
from acoustic_core.environment import Environment
from acoustic_core.evaluation import (
    assess_diffuse_field,
    calculate_modal_bandwidth,
    calculate_schroeder,
    evaluate_bonello,
    find_degenerate_dimensions,
    get_mode_distribution,
)
from acoustic_core.impulse import (
    build_impulse_response,
    calculate_energy,
    calculate_iso3382_parameters,
    generate_image_sources,
)
from acoustic_core.inverse import (
    current_absorption,
    design_treatment,
    missing_absorption,
    required_absorption,
    suggest_materials,
    suggest_placement,
    verify_treatment_plan,
)
from acoustic_core.isolation import (
    MATERIAL_PROPERTIES,
    NC_TARGETS,
    NR_TARGETS,
    THIRD_OCTAVE_BANDS_HZ,
    aggregate_flanking_paths,
    calculate_rw,
    calculate_stc,
    compare_target_by_use,
    critical_frequency,
    double_panel_tl_details,
    evaluate_nc,
    evaluate_nr,
    rectangular_lined_duct_attenuation,
    single_panel_tl_details,
)
from acoustic_core.measurement import (
    calibrate_alpha,
    compute_spectrogram,
    compute_waterfall,
    ess_deconvolution,
    estimate_modal_q,
    fractional_octave_edges,
    fractional_octave_filter,
    generate_ess,
    generate_wav_bytes,
    read_wav_bytes,
)
from acoustic_core.models import BANDAS_OCTAVA, Material, Room, Surface
from acoustic_core.presets import (
    CATEGORIAS,
    MATERIALES_PRESETS,
    AudienceConfig,
    audience_absorption_result,
    calculate_air_attenuation,
    calculate_audience_absorption,
    get_material_metadata,
    iso11654_diagnostics,
    material_catalog_records,
    search_materials,
)
from acoustic_core.pressure import (
    compute_pressure_map,
    compute_single_mode_grid,
    find_optimal_listening,
)
from acoustic_core.resonance import (
    calculate_modes,
    detect_degenerate_modes,
    detect_overlapping_modes,
)
from acoustic_core.reverberation import calculate_rt60_result, rt60_promedio_sabine, rt60_sabine

from .database import get_db
from .db_models import Calculation
from .dependencies import require_feature, verify_endpoint_access
from .jobs import (
    JOB_KINDS,
    active_job_count,
    cancel_job,
    enqueue_job,
    get_job_queue,
    get_job_status,
)
from .licensing import AuthenticatedPrincipal
from .object_service import (
    AssetIntegrityError,
    StorageQuotaExceeded,
    StoredAssetNotFound,
    create_asset,
    delete_asset,
    get_asset,
    list_assets,
    read_asset,
    reserve_multipart_asset,
    complete_multipart_asset,
    storage_metrics,
    storage_usage,
)
from .project_service import (
    ProjectNotFound,
    attach_asset,
    create_project,
    get_project,
    list_projects,
    project_assets,
)
from .rate_limit import enforce_rate_limit, get_rate_limiter, rate_limit_identity
from .schemas import (
    MAX_SIGNAL_SAMPLES,
    MAX_UPLOAD_BYTES,
    MAX_WAV_FRAMES,
    AbsorberAreaRequest,
    AbsorberAreaResponse,
    AbsorberResponse,
    AirAbsorptionRequest,
    AirAbsorptionResponse,
    AudienceAbsorptionRequest,
    AudienceAbsorptionDetailsResponse,
    BandValuesResponse,
    BoltAreaSchema,
    CalculateRequest,
    CalculateResponse,
    CalibrateRequest,
    CalibrateResponse,
    CoreBundleResponse,
    DeconvolutionResponse,
    DesignRatiosResponse,
    DesignTargetsResponse,
    DiffuseFieldSchema,
    DiffusionCoefficientRequest,
    DiffusionCoefficientResponse,
    DoublePanelResponse,
    DoublePanelTLRequest,
    DuctAttenuationRequest,
    DuctAttenuationResponse,
    ESSDeconvRequest,
    ESSRequest,
    ESSResponse,
    EnvironmentRequest,
    EnvironmentResponse,
    FEM2DRequest,
    FEM2DResponse,
    FEMModeSchema,
    FiniteImpedanceRequest,
    FiniteImpedanceResponse,
    FlankingRequest,
    FlankingResponse,
    FractionalOctaveFilterRequest,
    FractionalOctaveFilterResponse,
    HealthResponse,
    HelmholtzRequest,
    HelmholtzResponse,
    HybridRequest,
    HybridResponse,
    IRAnalysisRequest,
    IRAnalysisResponse,
    IRRequest,
    IRResponse,
    ISO11654Response,
    InverseDesignRequest,
    InverseDesignResponse,
    IsolationRatingsRequest,
    IsolationRatingsResponse,
    IsolationTargetsResponse,
    JobStatusResponse,
    JobSubmitRequest,
    LicenseStatusResponse,
    MaterialCategoriesResponse,
    MaterialCatalogMetadataSchema,
    MaterialClassificationRequest,
    MaterialResponse,
    MaterialSuggestion,
    MembraneRequest,
    MembraneResponse,
    MethodWarningSchema,
    ModalQRequest,
    ModalQResponse,
    MultipartCompleteRequest,
    MultipartUploadRequest,
    MultipartUploadResponse,
    NCEvaluationRequest,
    NREvaluationRequest,
    NoiseRatingResponse,
    PlacementSuggestion,
    PolygonFEMRequest,
    PolygonFEMResponse,
    PorousAbsorberRequest,
    PorousAbsorberResponse,
    ProjectCreateRequest,
    ProjectResponse,
    ProjectUpdateRequest,
    CalculationCreateRequest,
    CalculationResponse,
    PressureMapRequest,
    PressureMapResponse,
    QRDPolarRequest,
    QRDPolarResponse,
    QRDRequest,
    QRDResponse,
    RayTraceRequest,
    RayTraceResponse,
    SinglePanelResponse,
    SinglePanelTLRequest,
    SkylineRequest,
    SkylineResponse,
    SpectrogramRequest,
    SpectrogramResponse,
    StorageUsageResponse,
    StorageMetricsResponse,
    StoredAssetListResponse,
    StoredAssetResponse,
    TargetComparisonRequest,
    TargetComparisonResponse,
    TreatmentOptimizationRequest,
    TreatmentOptimizationResponse,
    TreatmentVerificationRequest,
    TreatmentVerificationResponse,
    WaterfallRequest,
    WaterfallResponse,
    WavAnalysisResponse,
)
from .storage import StorageBackend, get_storage


router = APIRouter()

NOMBRES_SUPERFICIES = ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"]
SUPERFICIE_AREAS = [
    lambda largo, ancho, alto: ancho * alto,
    lambda largo, ancho, alto: ancho * alto,
    lambda largo, ancho, alto: largo * alto,
    lambda largo, ancho, alto: largo * alto,
    lambda largo, ancho, alto: largo * ancho,
    lambda largo, ancho, alto: largo * ancho,
]
PUBLIC_DEFAULT_MATERIALS = (
    "Concreto",
    "Madera",
    "Yeso",
    "Vidrio",
    "Alfombra gruesa",
    "Cortina pesada",
    "Panel acústico",
    "Espuma acústica",
)


def _core_environment(data: EnvironmentRequest) -> Environment:
    return Environment(
        temperature_c=data.temperature_c,
        relative_humidity=data.relative_humidity,
        pressure_pa=data.pressure_pa,
    )


def _environment_response(environment: Environment) -> EnvironmentResponse:
    return EnvironmentResponse(
        temperature_c=environment.temperature_c,
        relative_humidity=environment.relative_humidity,
        pressure_pa=environment.pressure_pa,
        sound_speed_m_s=environment.sound_speed_m_s,
    )


def _build_room_with_warnings(data: CalculateRequest | PressureMapRequest | IRRequest | InverseDesignRequest | CalibrateRequest | RayTraceRequest | HybridRequest) -> tuple[Room, list[MethodWarningSchema]]:
    surfaces: list[Surface] = []
    method_warnings: list[MethodWarningSchema] = []
    for index, surface_request in enumerate(data.superficies):
        name = NOMBRES_SUPERFICIES[index]
        area = SUPERFICIE_AREAS[index](data.largo, data.ancho, data.alto)
        preset = MATERIALES_PRESETS.get(surface_request.material)
        overrides = surface_request.alphas

        if preset is None:
            if overrides is None or set(overrides) != set(BANDAS_OCTAVA):
                raise ValueError(
                    f"Unknown material '{surface_request.material}'; provide all six alpha bands "
                    "for an explicit custom material"
                )
            material = Material(nombre=surface_request.material, alphas=dict(overrides))
        elif overrides is None:
            material = preset
        else:
            merged = dict(preset.alpha)
            merged.update(overrides)
            material = Material(
                nombre=surface_request.material,
                alphas=merged,
                categoria=preset.categoria,
                provenance=preset.provenance,
            )
            if set(overrides) != set(BANDAS_OCTAVA):
                missing = [band for band in BANDAS_OCTAVA if band not in overrides]
                method_warnings.append(
                    MethodWarningSchema(
                        code="partial_absorption_merged",
                        method="material_input",
                        surface=name,
                        message=(
                            f"Custom alpha values on {name} override '{preset.nombre}'; "
                            f"preset values were retained at {', '.join(missing)} Hz."
                        ),
                        severity="info",
                    )
                )
        surfaces.append(Surface(nombre=name, area=area, material=material))

    room = Room(
        largo=data.largo,
        ancho=data.ancho,
        alto=data.alto,
        superficies=surfaces,
        uso=getattr(data, "uso", None),
        environment=_core_environment(data.environment),
    )
    return room, method_warnings


def _build_room(data: CalculateRequest | PressureMapRequest | IRRequest | InverseDesignRequest | CalibrateRequest | RayTraceRequest | HybridRequest) -> Room:
    return _build_room_with_warnings(data)[0]


def _compute_all(room: Room, *, include_air_attenuation: bool) -> dict[str, object]:
    modes = calculate_modes(room)
    detailed_rt60 = calculate_rt60_result(
        room,
        environment=room.environment,
        include_air_attenuation=include_air_attenuation,
    )
    rt60_bands = detailed_rt60.as_legacy_dict()
    rt60_mean = rt60_promedio_sabine(
        room,
        environment=room.environment,
        include_air_attenuation=include_air_attenuation,
    )
    modal_bandwidth = calculate_modal_bandwidth(rt60_mean)
    modes = detect_degenerate_modes(modes)
    modes = detect_overlapping_modes(modes, modal_bandwidth)
    frequencies = [mode.frecuencia for mode in modes]
    proportions = find_closest_ratio(room.largo, room.ancho, room.alto)

    objective = None
    target = get_rt60_target(room.uso) if room.uso else None
    if target:
        values = dict(target["valores"])
        objective = {
            "label": target["label"],
            "valores": values,
            "diferencias": {
                band: round(abs(rt60_bands[band]["Sabine"] - values[band]), 2)
                for band in BANDAS_OCTAVA
            },
        }

    method_warnings = []
    for estimate in detailed_rt60.estimates:
        for message in estimate.warnings:
            method_warnings.append(
                MethodWarningSchema(
                    code=(
                        "sabine_applicability"
                        if estimate.method == "Sabine" and "applicability" in message
                        else "unbounded_rt60"
                    ),
                    method=estimate.method,
                    band_hz=estimate.band,
                    message=message,
                )
            )

    bolt = evaluate_bolt_area(room.largo, room.ancho, room.alto)
    diffuse = assess_diffuse_field(modes)
    return {
        "modos": [mode.model_dump(mode="json") for mode in modes],
        "frecuencias": frequencies,
        "cantidad_modos": len(modes),
        "distribucion": get_mode_distribution(modes),
        "rt60_bandas": rt60_bands,
        "rt60_promedio": rt60_mean,
        "f_schroeder": calculate_schroeder(rt60_mean, room.volumen),
        "delta_f": modal_bandwidth,
        "bonello": evaluate_bonello(frequencies),
        "proporciones": proportions,
        "degeneracion_dimensiones": find_degenerate_dimensions(
            room.largo, room.ancho, room.alto
        ),
        "objetivo": objective,
        "method_warnings": method_warnings,
        "environment": _environment_response(room.environment),
        "sound_speed_m_s": room.sound_speed,
        "diffuse_field": DiffuseFieldSchema(**diffuse),
        "bolt_area": BoltAreaSchema(
            normalized_ratio=bolt.normalized_ratio,
            is_inside=bolt.is_inside,
            distance=bolt.distance,
            nearest_ratio=bolt.nearest_ratio,
            dimension_convention=DIMENSION_CONVENTION,
        ),
    }


def _material_to_response(material: Material) -> MaterialResponse:
    try:
        catalog = get_material_metadata(material.nombre).as_dict()
    except KeyError:
        catalog = None
    rating = iso11654_diagnostics(material.alpha).as_dict()
    uncertainty = None
    if material.uncertainty is not None:
        uncertainty = {
            "standard": material.uncertainty.value,
            "expanded": material.uncertainty.expanded,
            "unit": material.uncertainty.unit,
            "coverage_factor": material.uncertainty.coverage_factor,
            "confidence_level": material.uncertainty.confidence_level,
            "source": material.uncertainty.source,
        }
    return MaterialResponse(
        nombre=material.nombre,
        categoria=material.categoria,
        alphas=material.alpha,
        alpha_w=material.alpha_w,
        iso_class=material.iso_class,
        provenance=material.provenance,
        uncertainty=uncertainty,
        catalog=catalog,
        iso11654=rating,
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse()


@router.get(
    "/core-bundle",
    response_model=CoreBundleResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def core_bundle() -> dict[str, str]:
    core_dir = os.path.join(os.path.dirname(__file__), "..", "acoustic_core")
    files: dict[str, str] = {}
    for filename in sorted(os.listdir(core_dir)):
        if filename.endswith(".py") and filename != "__init__.py":
            path = os.path.join(core_dir, filename)
            with open(path, encoding="utf-8") as core_file:
                files[filename] = core_file.read()
    return files


@router.post(
    "/calculate",
    response_model=CalculateResponse,
    dependencies=[Depends(enforce_rate_limit)],
    openapi_extra={"security": [{}, {"APIKeyHeader": []}]},
)
async def calculate(data: CalculateRequest) -> CalculateResponse:
    room, input_warnings = _build_room_with_warnings(data)
    result = _compute_all(room, include_air_attenuation=data.include_air_attenuation)
    result["method_warnings"] = [*input_warnings, *result["method_warnings"]]
    return CalculateResponse(**result)


@router.get(
    "/materials/defaults",
    response_model=list[MaterialResponse],
    dependencies=[Depends(enforce_rate_limit)],
)
async def public_material_defaults() -> list[MaterialResponse]:
    return [_material_to_response(MATERIALES_PRESETS[name]) for name in PUBLIC_DEFAULT_MATERIALS]


@router.get(
    "/materials/defaults/categories",
    response_model=MaterialCategoriesResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def public_material_default_categories() -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {}
    for name in PUBLIC_DEFAULT_MATERIALS:
        material = MATERIALES_PRESETS[name]
        categories.setdefault(material.categoria, []).append(name)
    return categories


@router.get(
    "/materials",
    response_model=list[MaterialResponse],
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def list_materials(
    categoria: str = Query(default="", max_length=100),
    min_alpha_w: float = Query(default=0.0, ge=0, le=1),
    max_alpha_w: float = Query(default=1.0, ge=0, le=1),
    iso_class: str = Query(default="", max_length=20),
    query: str = Query(default="", max_length=200),
) -> list[MaterialResponse]:
    if min_alpha_w > max_alpha_w:
        raise HTTPException(status_code=422, detail="min_alpha_w must not exceed max_alpha_w")
    if query or categoria or min_alpha_w > 0 or max_alpha_w < 1 or iso_class:
        materials = search_materials(query, categoria, min_alpha_w, max_alpha_w, iso_class)
    else:
        materials = list(MATERIALES_PRESETS.values())
    return [_material_to_response(material) for material in materials]


@router.get(
    "/materials/categories",
    response_model=MaterialCategoriesResponse,
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def material_categories() -> dict[str, list[str]]:
    return CATEGORIAS


@router.get(
    "/materials/catalog",
    response_model=list[MaterialCatalogMetadataSchema],
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def material_catalog(
    include_aliases: bool = Query(default=True),
) -> list[dict[str, object]]:
    return material_catalog_records(include_aliases=include_aliases)


@router.post(
    "/materials/classify-iso11654",
    response_model=ISO11654Response,
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def classify_material_iso11654(
    data: MaterialClassificationRequest,
) -> dict[str, object]:
    return iso11654_diagnostics(data.practical_coefficients).as_dict()


@router.get(
    "/materials/{name}",
    response_model=MaterialResponse,
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def material_detail(name: str) -> MaterialResponse:
    material = MATERIALES_PRESETS.get(name)
    if material is None:
        raise HTTPException(status_code=404, detail=f"Material '{name}' no encontrado")
    return _material_to_response(material)


@router.get(
    "/design/ratios",
    response_model=DesignRatiosResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def design_ratios() -> dict[str, tuple[float, float, float]]:
    return PROPORCIONES


@router.get(
    "/design/targets",
    response_model=DesignTargetsResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def design_targets() -> dict[str, dict[str, object]]:
    return RT60_OBJETIVOS


@router.post(
    "/design/air-absorption",
    response_model=AirAbsorptionResponse,
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def air_absorption(data: AirAbsorptionRequest) -> AirAbsorptionResponse:
    environment = Environment(data.temp_celsius, data.humidity, data.pressure_pa)
    attenuation = {
        band: calculate_air_attenuation(
            float(band),
            data.humidity,
            data.temp_celsius,
            pressure_pa=data.pressure_pa,
        )
        for band in BANDAS_OCTAVA
    }
    return AirAbsorptionResponse(
        coeficientes={
            band: round(result.energy_decay_m_inv, 8)
            for band, result in attenuation.items()
        },
        attenuation_db_per_m={
            band: round(result.attenuation_db_per_m, 8)
            for band, result in attenuation.items()
        },
        humidity=data.humidity,
        temp_celsius=data.temp_celsius,
        pressure_pa=data.pressure_pa,
        sound_speed_m_s=environment.sound_speed_m_s,
    )


@router.post(
    "/design/audience-absorption",
    response_model=BandValuesResponse,
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def audience_absorption(data: AudienceAbsorptionRequest) -> dict[str, float]:
    config = AudienceConfig(
        num_people=data.num_people,
        seated=data.seated,
        upholstered=data.upholstered,
        occupied=data.occupied,
    )
    return calculate_audience_absorption(config)


@router.post(
    "/design/audience-absorption/details",
    response_model=AudienceAbsorptionDetailsResponse,
    dependencies=[Depends(require_feature("materials")), Depends(enforce_rate_limit)],
)
async def audience_absorption_details(
    data: AudienceAbsorptionRequest,
) -> AudienceAbsorptionDetailsResponse:
    result = audience_absorption_result(
        AudienceConfig(
            num_people=data.num_people,
            seated=data.seated,
            upholstered=data.upholstered,
            occupied=data.occupied,
        )
    )
    return AudienceAbsorptionDetailsResponse(**result.as_dict())


@router.post(
    "/design/absorbers/porous",
    response_model=PorousAbsorberResponse,
    dependencies=[Depends(require_feature("absorbers")), Depends(enforce_rate_limit)],
)
async def porous_absorber(data: PorousAbsorberRequest) -> PorousAbsorberResponse:
    environment = _core_environment(data.environment)
    result = porous_absorber_estimate(
        data.thickness_m,
        data.flow_resistivity,
        data.density_kgm3,
        air_gap_m=data.air_gap_m,
        incidence_angle_deg=data.incidence_angle_deg,
        strict_validity=data.strict_validity,
        sound_speed_m_s=environment.sound_speed_m_s,
        air_density_kgm3=data.air_density_kgm3,
    )
    return PorousAbsorberResponse(
        **result,
        environment=_environment_response(environment),
    )


@router.post(
    "/design/absorbers/helmholtz",
    response_model=HelmholtzResponse,
    dependencies=[Depends(require_feature("absorbers")), Depends(enforce_rate_limit)],
)
async def helmholtz_absorber(data: HelmholtzRequest) -> HelmholtzResponse:
    environment = _core_environment(data.environment)
    result = helmholtz_resonator(
        data.neck_area_m2,
        data.cavity_volume_m3,
        data.neck_length_m,
        data.neck_radius_m,
        panel_area_m2=data.panel_area_m2,
        open_area_ratio=data.open_area_ratio,
        hole_count=data.hole_count,
        end_correction_coefficient=data.end_correction_coefficient,
        quality_factor=data.quality_factor,
        loss_factor=data.loss_factor,
        peak_absorption=data.peak_absorption,
        sound_speed_m_s=environment.sound_speed_m_s,
    )
    return HelmholtzResponse(**result, environment=_environment_response(environment))


@router.post(
    "/design/absorbers/membrane",
    response_model=MembraneResponse,
    dependencies=[Depends(require_feature("absorbers")), Depends(enforce_rate_limit)],
)
async def membrane_absorber_endpoint(data: MembraneRequest) -> MembraneResponse:
    result = membrane_absorber(
        data.mass_per_area_kgm2,
        data.air_gap_m,
        quality_factor=data.quality_factor,
        loss_factor=data.loss_factor,
        surface_tension_n_m=data.surface_tension_n_m,
        panel_span_m=data.panel_span_m,
        peak_absorption=data.peak_absorption,
    )
    return MembraneResponse(**result)


@router.post(
    "/design/absorbers/recommended-area",
    response_model=AbsorberAreaResponse,
    dependencies=[Depends(require_feature("absorbers")), Depends(enforce_rate_limit)],
)
async def absorber_recommended_area(data: AbsorberAreaRequest) -> AbsorberAreaResponse:
    result = recommended_absorber_area(
        data.absorption_coefficients,
        data.missing_absorption_m2_sabins,
        existing_surface_alpha=data.existing_surface_alpha,
        installation_mode=data.installation_mode,
        available_area_m2=data.available_area_m2,
    )
    return AbsorberAreaResponse(**result)


@router.post(
    "/design/diffusers/qrd",
    response_model=QRDResponse,
    dependencies=[Depends(require_feature("diffusers")), Depends(enforce_rate_limit)],
)
async def qrd_calculator(data: QRDRequest) -> QRDResponse:
    result = qrd_well_depths(data.design_freq_hz, data.prime_n, data.well_width_m)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    result["diffusion_coefficient"] = estimate_diffusion_coefficient(
        data.design_freq_hz, result["max_depth_m"]
    )
    return QRDResponse(**result)


@router.post(
    "/design/diffusers/skyline",
    response_model=SkylineResponse,
    dependencies=[Depends(require_feature("diffusers")), Depends(enforce_rate_limit)],
)
async def skyline_calculator(data: SkylineRequest) -> SkylineResponse:
    result = skyline_well_depths(data.design_freq_hz, data.grid_n, data.well_size_m)
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    return SkylineResponse(**result)


@router.post(
    "/design/diffusers/diffusion",
    response_model=DiffusionCoefficientResponse,
    dependencies=[Depends(require_feature("diffusers")), Depends(enforce_rate_limit)],
)
async def diffuser_diffusion_coefficient(
    data: DiffusionCoefficientRequest,
) -> DiffusionCoefficientResponse:
    result = diffusion_coefficient_diagnostics(
        data.polar_response,
        reference_response=data.reference_response,
        response_unit=data.response_unit,
    )
    return DiffusionCoefficientResponse(**result)


@router.post(
    "/design/diffusers/qrd/polar-response",
    response_model=QRDPolarResponse,
    dependencies=[Depends(require_feature("diffusers")), Depends(enforce_rate_limit)],
)
async def qrd_polar_response(data: QRDPolarRequest) -> QRDPolarResponse:
    environment = _core_environment(data.environment)
    response = simulate_qrd_polar_response(
        data.well_depths_m,
        data.frequency_hz,
        data.well_width_m,
        angles_deg=data.angles_deg,
        sound_speed_m_s=environment.sound_speed_m_s,
    )
    return QRDPolarResponse(
        samples=[
            {"angle_deg": angle, "normalized_pressure": pressure}
            for angle, pressure in response.items()
        ],
        frequency_hz=data.frequency_hz,
        well_width_m=data.well_width_m,
        environment=_environment_response(environment),
        estimate_label="engineering_estimate_not_iso_test_or_certification",
    )


def _third_octave_frequencies() -> tuple[float, ...]:
    return tuple(float(value) for value in THIRD_OCTAVE_BANDS_HZ)


@router.post(
    "/design/isolation/single-panel",
    response_model=SinglePanelResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def single_panel(data: SinglePanelTLRequest) -> SinglePanelResponse:
    if data.material_type not in MATERIAL_PROPERTIES and not all(
        value is not None
        for value in (data.density_kgm3, data.young_modulus_pa, data.poisson_ratio)
    ):
        raise ValueError(
            f"Unknown panel material_type '{data.material_type}'; provide all structural properties"
        )
    details = single_panel_tl_details(
        data.mass_per_area_kgm2,
        data.thickness_m,
        data.material_type,
        density_kgm3=data.density_kgm3,
        young_modulus_pa=data.young_modulus_pa,
        poisson_ratio=data.poisson_ratio,
        loss_factor=data.loss_factor,
        frequencies_hz=_third_octave_frequencies(),
    )
    stc = calculate_stc(details["tl"])
    rw = calculate_rw(details["tl"])
    if data.c_l_material > 0:
        fc_hz = critical_frequency(data.thickness_m, data.c_l_material)
    else:
        fc_hz = details["critical_frequency_hz"]
    return SinglePanelResponse(
        tl={band: details["tl"][band] for band in BANDAS_OCTAVA},
        third_octave_tl=details["tl"],
        fc_hz=fc_hz,
        mass_per_area_kgm2=data.mass_per_area_kgm2,
        thickness_m=data.thickness_m,
        stc=stc["stc"],
        rw=rw["rw"],
        c=rw["c"],
        ctr=rw["ctr"],
        stc_details=stc,
        rw_details=rw,
        mass_law_asymptote_db=details["mass_law_asymptote_db"],
        coincidence_correction_db=details["coincidence_correction_db"],
        coincidence_depth_db=details["coincidence_depth_db"],
        material_type=details["material_type"],
        material_properties=details["material_properties"],
        surface_mass_from_density_kgm2=details["surface_mass_from_density_kgm2"],
        assumptions=details["assumptions"],
        is_estimate=details["is_estimate"],
        reference=details["reference"],
    )


@router.post(
    "/design/isolation/double-panel",
    response_model=DoublePanelResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def double_panel(data: DoublePanelTLRequest) -> DoublePanelResponse:
    details = double_panel_tl_details(
        data.m1_kgm2,
        data.m2_kgm2,
        data.gap_m,
        data.stud_connection,
        cavity_absorption=data.cavity_absorption,
        bridge_penalty_db=data.bridge_penalty_db,
        frequencies_hz=_third_octave_frequencies(),
    )
    stc = calculate_stc(details["tl"])
    rw = calculate_rw(details["tl"])
    return DoublePanelResponse(
        tl={band: details["tl"][band] for band in BANDAS_OCTAVA},
        third_octave_tl=details["tl"],
        f0_hz=details["mass_air_mass_resonance_hz"],
        m1_kgm2=data.m1_kgm2,
        m2_kgm2=data.m2_kgm2,
        gap_m=data.gap_m,
        stud_connection=data.stud_connection,
        stc=stc["stc"],
        rw=rw["rw"],
        c=rw["c"],
        ctr=rw["ctr"],
        stc_details=stc,
        rw_details=rw,
        combined_mass_asymptote_db=details["combined_mass_asymptote_db"],
        independent_leaves_asymptote_db=details["independent_leaves_asymptote_db"],
        resonance_penalty_db=details["resonance_penalty_db"],
        cavity_absorption_gain_db=details["cavity_absorption_gain_db"],
        bridge_penalty_db=details["bridge_penalty_db"],
        regime_by_band=details["regime_by_band"],
        assumptions=details["assumptions"],
        is_estimate=details["is_estimate"],
        reference=details["reference"],
    )


@router.post(
    "/design/isolation/ratings",
    response_model=IsolationRatingsResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def isolation_ratings(data: IsolationRatingsRequest) -> IsolationRatingsResponse:
    return IsolationRatingsResponse(stc=calculate_stc(data.tl), rw=calculate_rw(data.tl))


@router.post(
    "/design/isolation/nc",
    response_model=NoiseRatingResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def nc_evaluation(data: NCEvaluationRequest) -> NoiseRatingResponse:
    return NoiseRatingResponse(**evaluate_nc(data.spl))


@router.post(
    "/design/isolation/nr",
    response_model=NoiseRatingResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def nr_evaluation(data: NREvaluationRequest) -> NoiseRatingResponse:
    return NoiseRatingResponse(**evaluate_nr(data.spl))


@router.get(
    "/design/isolation/nc-targets",
    response_model=IsolationTargetsResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def nc_targets() -> dict[str, dict[str, str | int]]:
    return NC_TARGETS


@router.get(
    "/design/isolation/nr-targets",
    response_model=IsolationTargetsResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def nr_targets() -> dict[str, dict[str, str | int]]:
    return {
        name: {
            **target,
            "basis": "public recommended NR application; project target, not certification",
        }
        for name, target in NR_TARGETS.items()
    }


@router.post(
    "/design/isolation/target-comparison",
    response_model=TargetComparisonResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def isolation_target_comparison(
    data: TargetComparisonRequest,
) -> TargetComparisonResponse:
    result = compare_target_by_use(
        data.uso,
        nc=data.nc,
        nr=data.nr,
        stc=data.stc,
        rw=data.rw,
    )
    return TargetComparisonResponse(**result)


@router.post(
    "/design/isolation/duct-attenuation",
    response_model=DuctAttenuationResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def duct_attenuation(data: DuctAttenuationRequest) -> DuctAttenuationResponse:
    result = rectangular_lined_duct_attenuation(
        data.width_m,
        data.height_m,
        data.length_m,
        data.absorption_coefficients,
        lined_perimeter_fraction=data.lined_perimeter_fraction,
        frequencies_hz=data.frequencies_hz,
    )
    return DuctAttenuationResponse(**result)


@router.post(
    "/design/isolation/flanking",
    response_model=FlankingResponse,
    dependencies=[Depends(require_feature("isolation")), Depends(enforce_rate_limit)],
)
async def flanking_estimate(data: FlankingRequest) -> FlankingResponse:
    result = aggregate_flanking_paths(data.direct_tl_db, data.flanking_paths_tl_db)
    return FlankingResponse(**result)


@router.post(
    "/design/inverse",
    response_model=InverseDesignResponse,
    dependencies=[Depends(require_feature("inverse_design")), Depends(enforce_rate_limit)],
)
async def inverse_design(data: InverseDesignRequest) -> InverseDesignResponse:
    room = _build_room(data)
    target = get_rt60_target(data.target_uso)
    if target is None:
        raise HTTPException(status_code=400, detail=f"Uso objetivo '{data.target_uso}' no válido")
    targets = target["valores"]
    placements = []
    if data.include_placement:
        modes = calculate_modes(room, f_max=300.0)
        pressure = compute_pressure_map(room, modos=modes, max_freq=300.0)
        placements = suggest_placement(room, data.target_uso, pressure)
    return InverseDesignResponse(
        current_absorption=current_absorption(room),
        required_absorption=required_absorption(room.volumen, targets),
        missing_absorption=missing_absorption(room, targets),
        material_suggestions=[
            MaterialSuggestion(**suggestion)
            for suggestion in suggest_materials(room, data.target_uso)
            if "mensaje" not in suggestion
        ],
        placement_suggestions=[PlacementSuggestion(**placement) for placement in placements],
    )


@router.post(
    "/design/inverse/verify",
    response_model=TreatmentVerificationResponse,
    dependencies=[Depends(require_feature("inverse_design")), Depends(enforce_rate_limit)],
)
async def verify_inverse_treatment(
    data: TreatmentVerificationRequest,
) -> TreatmentVerificationResponse:
    unknown = [
        treatment.material
        for treatment in data.treatments
        if treatment.material not in MATERIALES_PRESETS
    ]
    if unknown:
        raise ValueError(f"Unknown treatment material(s): {', '.join(sorted(set(unknown)))}")
    room = _build_room(data)
    result = verify_treatment_plan(
        room,
        data.target_rt60,
        [treatment.model_dump() for treatment in data.treatments],
    )
    return TreatmentVerificationResponse(**result)


@router.post(
    "/design/inverse/optimize",
    response_model=TreatmentOptimizationResponse,
    dependencies=[Depends(require_feature("inverse_design")), Depends(enforce_rate_limit)],
)
async def optimize_inverse_treatment(
    data: TreatmentOptimizationRequest,
) -> TreatmentOptimizationResponse:
    if data.candidate_materials:
        unknown = [
            material
            for material in data.candidate_materials
            if material not in MATERIALES_PRESETS
        ]
        if unknown:
            raise ValueError(
                f"Unknown candidate material(s): {', '.join(sorted(set(unknown)))}"
            )
    room = _build_room(data)
    pressure = None
    if data.include_pressure_map:
        modes = calculate_modes(room, f_max=300.0)
        pressure = compute_pressure_map(
            room,
            modos=modes,
            max_freq=300.0,
            grid_size=30,
        )
    result = design_treatment(
        room,
        data.target_uso,
        candidate_materials=data.candidate_materials,
        available_area_m2=data.available_area_m2,
        installation_mode=data.installation_mode,
        max_materials=data.max_materials,
        area_step_m2=data.area_step_m2,
        pressure_map_data=pressure,
    )
    return TreatmentOptimizationResponse(**result)


@router.post(
    "/pressure-map",
    response_model=PressureMapResponse,
    dependencies=[Depends(enforce_rate_limit)],
    openapi_extra={"security": [{}, {"APIKeyHeader": []}]},
)
async def pressure_map(data: PressureMapRequest) -> PressureMapResponse:
    room = _build_room(data)
    modes = calculate_modes(room, f_max=data.max_freq)
    if data.mode_indices is not None:
        result = compute_single_mode_grid(
            room,
            *data.mode_indices,
            ear_height=data.ear_height,
            grid_size=data.grid_size,
        )
        nx, ny, nz = data.mode_indices
        displayed_frequency = room.sound_speed / 2.0 * math.sqrt(
            (nx / room.largo) ** 2
            + (ny / room.ancho) ** 2
            + (nz / room.alto) ** 2
        )
        number_of_modes = 1
        energy = None
    else:
        result = compute_pressure_map(
            room,
            modos=modes,
            max_freq=data.max_freq,
            ear_height=data.ear_height,
            grid_size=data.grid_size,
        )
        displayed_frequency = data.max_freq
        number_of_modes = result["num_modos"]
        energy = result["energy"]

    optimal = find_optimal_listening(
        room,
        modos=modes,
        max_freq=data.max_freq,
        ear_height=data.ear_height,
    )
    return PressureMapResponse(
        grid_x=result["grid_x"],
        grid_y=result["grid_y"],
        pressure=result["pressure"],
        magnitude=result["magnitude"],
        energy=energy,
        signed_pressure=result.get("signed_pressure"),
        quantity=result["quantity"],
        max_freq=displayed_frequency,
        ear_height=data.ear_height,
        num_modos=number_of_modes,
        optimal_listening=optimal,
        warnings=result.get("warnings", []),
        environment=_environment_response(room.environment),
    )


@router.post(
    "/impulse-response",
    response_model=IRResponse,
    dependencies=[Depends(require_feature("ism")), Depends(enforce_rate_limit)],
)
async def impulse_response(data: IRRequest) -> IRResponse:
    room = _build_room(data)
    image_sources = generate_image_sources(
        room,
        data.source,
        data.receiver,
        max_order=data.max_order,
        c=room.sound_speed,
    )
    energetic_sources = calculate_energy(image_sources, room, data.band)
    impulse = build_impulse_response(
        energetic_sources,
        fs=data.sample_rate,
        duration_s=data.duration_s,
        banda_energia=data.band,
        room=room,
        normalize=data.normalize,
    )
    parameters = calculate_iso3382_parameters(
        impulse["impulse_response"],
        data.sample_rate,
        impulse["direct_delay_ms"],
        metric_context="predicted_model",
    )
    return IRResponse(
        impulse_response=impulse["impulse_response"],
        sample_rate=data.sample_rate,
        direct_delay_ms=impulse["direct_delay_ms"],
        direct_delay_s=impulse["direct_delay_s"],
        direct_sample=impulse["direct_sample"],
        arrivals_rendered=impulse["arrivals_rendered"],
        image_source_count=len(image_sources),
        impulse_representation=impulse["impulse_representation"],
        normalization_gain=impulse["normalization_gain"],
        band=data.band,
        parameters=parameters,
        environment=_environment_response(room.environment),
    )


def _generate_ess(data: ESSRequest) -> list[float]:
    return generate_ess(
        data.f1_hz,
        data.f2_hz,
        data.duration_s,
        data.sample_rate,
        amplitude=data.amplitude,
        fade_in_s=data.fade_in_s,
        fade_out_s=data.fade_out_s,
        headroom_db=data.headroom_db,
    )


@router.post(
    "/measurement/ess",
    response_model=ESSResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def generate_ess_endpoint(data: ESSRequest) -> ESSResponse:
    signal = _generate_ess(data)
    preview = signal[:5000]
    return ESSResponse(
        signal=preview,
        sample_rate=data.sample_rate,
        duration_s=data.duration_s,
        f1_hz=data.f1_hz,
        f2_hz=data.f2_hz,
        total_samples=len(signal),
        preview_truncated=len(preview) < len(signal),
    )


@router.post(
    "/measurement/ess/wav",
    response_class=StreamingResponse,
    responses={200: {"content": {"audio/wav": {}}}},
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
@router.post(
    "/measurement/ess.wav",
    response_class=StreamingResponse,
    include_in_schema=False,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def generate_ess_wav(data: ESSRequest) -> StreamingResponse:
    signal = _generate_ess(data)
    wav = generate_wav_bytes(
        signal,
        data.sample_rate,
        bit_depth=data.bit_depth,
        encoding=data.encoding,
    )
    filename = f"ess-{data.f1_hz:g}-{data.f2_hz:g}Hz-{data.sample_rate}Hz.wav"
    return StreamingResponse(
        io.BytesIO(wav),
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(wav)),
        },
    )


@router.post(
    "/measurement/deconvolve",
    response_model=DeconvolutionResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def deconvolve_ess(data: ESSDeconvRequest) -> DeconvolutionResponse:
    impulse = ess_deconvolution(
        data.response,
        data.ess,
        data.sample_rate,
        f1_hz=data.f1_hz,
        f2_hz=data.f2_hz,
        align=data.align,
        regularization=data.regularization,
    )
    return DeconvolutionResponse(
        impulse_response=impulse,
        sample_rate=data.sample_rate,
        aligned=data.align,
        total_samples=len(impulse),
    )


async def _bounded_upload(upload: UploadFile) -> bytes:
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    await upload.close()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"WAV upload exceeds {MAX_UPLOAD_BYTES} bytes",
        )
    if not data:
        raise HTTPException(status_code=422, detail="WAV upload is empty")
    return data


def _channel_value(channel: str) -> int | str:
    if channel == "mix":
        return "mix"
    try:
        parsed = int(channel)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="channel must be an integer or 'mix'") from exc
    if parsed < 0 or parsed > 63:
        raise HTTPException(status_code=422, detail="channel must be between 0 and 63")
    return parsed


async def _parse_uploaded_wav(upload: UploadFile, channel: str) -> tuple[dict[str, object], list[float]]:
    parsed = read_wav_bytes(
        await _bounded_upload(upload),
        channel=_channel_value(channel),
        max_frames=MAX_WAV_FRAMES,
    )
    samples = parsed["samples"]
    if not isinstance(samples, list) or (samples and isinstance(samples[0], list)):
        raise ValueError("WAV channel selection did not produce a mono signal")
    return parsed, samples


def _wav_response(
    filename: str | None,
    parsed: Mapping[str, object],
    samples: list[float],
    parameters: dict[str, object] | None,
) -> WavAnalysisResponse:
    preview = samples[:5000]
    return WavAnalysisResponse(
        filename=filename,
        sample_rate=parsed["sample_rate"],
        num_channels=parsed["num_channels"],
        num_frames=parsed["num_frames"],
        bits_per_sample=parsed["bits_per_sample"],
        audio_format=parsed["audio_format"],
        selected_channel=parsed["selected_channel"],
        samples_preview=preview,
        preview_truncated=len(preview) < len(samples),
        parameters=parameters,
    )


@router.post(
    "/measurement/wav/import",
    response_model=WavAnalysisResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def import_wav(
    file: UploadFile = File(...),
    channel: str = Query(default="0", max_length=8),
) -> WavAnalysisResponse:
    filename = file.filename
    parsed, samples = await _parse_uploaded_wav(file, channel)
    return _wav_response(filename, parsed, samples, None)


@router.post(
    "/measurement/wav/analyze",
    response_model=WavAnalysisResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def analyze_wav(
    file: UploadFile = File(...),
    channel: str = Query(default="0", max_length=8),
    direct_delay_ms: float = Query(default=0, ge=0, le=60_000),
) -> WavAnalysisResponse:
    filename = file.filename
    parsed, samples = await _parse_uploaded_wav(file, channel)
    parameters = calculate_iso3382_parameters(
        samples,
        parsed["sample_rate"],
        direct_delay_ms,
        metric_context="measured",
    )
    return _wav_response(filename, parsed, samples, parameters)


@router.post(
    "/measurement/deconvolve-wav",
    response_class=StreamingResponse,
    responses={200: {"content": {"audio/wav": {}}}},
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def deconvolve_wav(
    response_file: UploadFile = File(...),
    ess_file: UploadFile = File(...),
    f1_hz: float = Form(..., gt=0),
    f2_hz: float = Form(..., gt=0),
    align: bool = Form(True),
    regularization: float = Form(1e-10, gt=0, lt=1),
    bit_depth: int = Form(16),
) -> StreamingResponse:
    response_parsed, response = await _parse_uploaded_wav(response_file, "0")
    ess_parsed, ess = await _parse_uploaded_wav(ess_file, "0")
    sample_rate = response_parsed["sample_rate"]
    if sample_rate != ess_parsed["sample_rate"]:
        raise HTTPException(status_code=422, detail="response and ESS sample rates must match")
    if f1_hz >= f2_hz or f2_hz >= sample_rate / 2:
        raise HTTPException(status_code=422, detail="require f1_hz < f2_hz < Nyquist")
    if len(response) + len(ess) > MAX_SIGNAL_SAMPLES:
        raise HTTPException(status_code=422, detail="WAV deconvolution exceeds sample bound")
    if bit_depth not in (16, 24, 32):
        raise HTTPException(status_code=422, detail="bit_depth must be 16, 24, or 32")
    impulse = ess_deconvolution(
        response,
        ess,
        sample_rate,
        f1_hz=f1_hz,
        f2_hz=f2_hz,
        align=align,
        regularization=regularization,
    )
    wav = generate_wav_bytes(impulse, sample_rate, bit_depth=bit_depth)
    return StreamingResponse(
        io.BytesIO(wav),
        media_type="audio/wav",
        headers={
            "Content-Disposition": 'attachment; filename="deconvolved-ir.wav"',
            "Content-Length": str(len(wav)),
        },
    )


@router.post(
    "/measurement/filter",
    response_model=FractionalOctaveFilterResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def fractional_filter(
    data: FractionalOctaveFilterRequest,
) -> FractionalOctaveFilterResponse:
    filtered = fractional_octave_filter(
        data.signal, data.sample_rate, data.center_hz, data.fraction
    )
    return FractionalOctaveFilterResponse(
        signal=filtered,
        sample_rate=data.sample_rate,
        center_hz=data.center_hz,
        fraction=data.fraction,
        band_edges_hz=fractional_octave_edges(data.center_hz, data.fraction),
    )


@router.post(
    "/measurement/ir/analyze",
    response_model=IRAnalysisResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def analyze_ir(data: IRAnalysisRequest) -> IRAnalysisResponse:
    parameters = calculate_iso3382_parameters(
        data.ir,
        data.sample_rate,
        data.direct_delay_ms,
        metric_context=data.metric_context,
    )
    return IRAnalysisResponse(
        sample_rate=data.sample_rate,
        total_samples=len(data.ir),
        parameters=parameters,
    )


@router.post(
    "/measurement/waterfall",
    response_model=WaterfallResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def waterfall_analysis(data: WaterfallRequest) -> WaterfallResponse:
    result = compute_waterfall(
        data.ir,
        data.sample_rate,
        data.duration_s,
        fraction=data.fraction,
        centers_hz=data.centers_hz,
        time_step_s=data.time_step_s,
        floor_db=data.floor_db,
    )
    return WaterfallResponse(**result)


@router.post(
    "/measurement/spectrogram",
    response_model=SpectrogramResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def spectrogram_analysis(data: SpectrogramRequest) -> SpectrogramResponse:
    result = compute_spectrogram(
        data.signal,
        data.sample_rate,
        data.window_size,
        data.hop_size,
        floor_db=data.floor_db,
        max_frames=data.max_frames,
    )
    return SpectrogramResponse(**result)


@router.post(
    "/measurement/modal-q",
    response_model=ModalQResponse,
    dependencies=[Depends(require_feature("measurement")), Depends(enforce_rate_limit)],
)
async def modal_q_analysis(data: ModalQRequest) -> ModalQResponse:
    result = estimate_modal_q(
        data.signal,
        data.sample_rate,
        data.target_frequency_hz,
        cycles_per_window=data.cycles_per_window,
        dynamic_range_db=data.dynamic_range_db,
    )
    return ModalQResponse(**result)


@router.post(
    "/measurement/calibrate",
    response_model=CalibrateResponse,
    dependencies=[Depends(require_feature("calibration")), Depends(enforce_rate_limit)],
)
async def calibrate_model(data: CalibrateRequest) -> CalibrateResponse:
    room = _build_room(data)
    calibrated = calibrate_alpha(
        room,
        data.measured_rt60,
        iterations=data.iterations,
    )
    diagnostics = calibrated.pop("diagnostics")
    return CalibrateResponse(
        calibrated_alphas=calibrated,
        diagnostics=diagnostics,
        measured_rt60=data.measured_rt60,
    )


def _finite_impedance_analysis(data: FiniteImpedanceRequest) -> FiniteImpedanceResponse:
    from acoustic_numerics.finite_impedance import rt60_from_decay_rate, solve_axial_modes

    environment = _core_environment(data.environment)
    sound_speed = environment.sound_speed_m_s
    impedance = complex(data.Z_wall, data.Z_wall_imag)
    axial_roots = solve_axial_modes(
        data.L_m,
        impedance,
        num_modes=data.max_order,
        density_kg_m3=data.density_kgm3,
        sound_speed_m_s=sound_speed,
    )
    axial = [
        {
            "n": mode.mode_index,
            "frequency_hz": mode.frequency_real_hz,
            "frequency_imag_hz": mode.frequency_imag_hz,
            "rigid_frequency_hz": mode.rigid_frequency_hz,
            "damping_neper_s": mode.decay_rate_neper_s,
            "decay_rate_neper_s": mode.decay_rate_neper_s,
            "rt60_estimate_s": mode.rt60_s if math.isfinite(mode.rt60_s) else 0.0,
            "shift_hz": mode.frequency_real_hz - mode.rigid_frequency_hz,
            "residual": mode.residual,
            "converged": mode.converged,
            "boundary_configuration": "rigid at x=0; locally reacting impedance at x=L",
        }
        for mode in axial_roots
    ]
    dimensions = (data.L_m, data.W_m, data.H_m)
    roots_by_axis = {
        axis: solve_axial_modes(
            dimension,
            impedance,
            num_modes=data.max_order,
            density_kg_m3=data.density_kgm3,
            sound_speed_m_s=sound_speed,
        )
        for axis, dimension in enumerate(dimensions)
    }
    room_modes = []
    for nx in range(data.max_order + 1):
        for ny in range(data.max_order + 1):
            for nz in range(data.max_order + 1):
                indices = (nx, ny, nz)
                if indices == (0, 0, 0):
                    continue
                components = [
                    0.0j if order == 0 else roots_by_axis[axis][order - 1].wavenumber_per_m
                    for axis, order in enumerate(indices)
                ]
                wavenumber = cmath.sqrt(sum(component * component for component in components))
                if wavenumber.real < 0 or (wavenumber.real == 0 and wavenumber.imag > 0):
                    wavenumber = -wavenumber
                frequency = sound_speed * wavenumber / (2.0 * math.pi)
                rigid_wavenumber_squared = sum(
                    (order * math.pi / dimension) ** 2
                    for order, dimension in zip(indices, dimensions)
                )
                rigid_frequency = (
                    sound_speed * math.sqrt(rigid_wavenumber_squared) / (2.0 * math.pi)
                )
                decay_rate = max(0.0, -sound_speed * wavenumber.imag)
                active_residuals = [
                    roots_by_axis[axis][order - 1].residual
                    for axis, order in enumerate(indices)
                    if order > 0
                ]
                rt60 = rt60_from_decay_rate(decay_rate)
                room_modes.append(
                    {
                        "indices": indices,
                        "frequency_hz": frequency.real,
                        "frequency_imag_hz": frequency.imag,
                        "rigid_frequency_hz": rigid_frequency,
                        "damping": decay_rate,
                        "damping_neper_s": decay_rate,
                        "rt60_estimate_s": rt60 if math.isfinite(rt60) else 0.0,
                        "residual": max(active_residuals, default=0.0),
                        "model": "separable active-axis impedance approximation",
                    }
                )
    room_modes.sort(key=lambda mode: mode["frequency_hz"])
    return FiniteImpedanceResponse(
        axial_modes=axial,
        room_modes=room_modes,
        Z_wall=data.Z_wall,
        Z_wall_imag=data.Z_wall_imag,
        density_kgm3=data.density_kgm3,
        environment=_environment_response(environment),
        research_status=(
            "Research impedance-root model; validate boundary impedance and modal convergence."
        ),
    )


@router.post(
    "/numerical/finite-impedance",
    response_model=FiniteImpedanceResponse,
    dependencies=[Depends(require_feature("numerical")), Depends(enforce_rate_limit)],
)
async def finite_impedance_analysis(
    data: FiniteImpedanceRequest,
) -> FiniteImpedanceResponse:
    return _finite_impedance_analysis(data)


def _fem_mode_payload(data: FEM2DRequest) -> FEM2DResponse:
    from acoustic_numerics.fem2d import masked_rectangle_mesh, rectangle_mesh, solve_fem_modes

    environment = _core_environment(data.environment)
    exclusions = [region.model_dump() for region in data.exclude_regions]
    mesh = (
        masked_rectangle_mesh(
            data.width, data.height, data.grid_nx, data.grid_ny, exclusions
        )
        if exclusions
        else rectangle_mesh(data.width, data.height, data.grid_nx, data.grid_ny)
    )
    boundary_impedance = (
        None
        if data.boundary_impedance_real is None
        else complex(data.boundary_impedance_real, data.boundary_impedance_imag)
    )
    result = solve_fem_modes(
        mesh,
        num_modes=data.num_modes,
        sound_speed_m_s=environment.sound_speed_m_s,
        density_kg_m3=data.density_kgm3,
        boundary_impedance=boundary_impedance,
    )
    grid_x = [index * data.width / (data.grid_nx - 1) for index in range(data.grid_nx)]
    grid_y = [index * data.height / (data.grid_ny - 1) for index in range(data.grid_ny)]
    modes = []
    for mode in result.modes:
        real_shape = [float(value.real) for value in mode.shape]
        scale = max((abs(value) for value in real_shape), default=1.0) or 1.0
        shape = [[0.0 for _ in range(data.grid_nx)] for _ in range(data.grid_ny)]
        for node, value in zip(mesh.nodes, real_shape):
            x_index = int(round(float(node[0]) / data.width * (data.grid_nx - 1)))
            y_index = int(round(float(node[1]) / data.height * (data.grid_ny - 1)))
            if 0 <= x_index < data.grid_nx and 0 <= y_index < data.grid_ny:
                shape[y_index][x_index] = value / scale
        modes.append(
            FEMModeSchema(
                mode=mode.mode_index,
                frequency_hz=mode.frequency_hz,
                frequency_imag_hz=mode.complex_frequency_hz.imag,
                decay_rate_neper_s=mode.decay_rate_neper_s,
                rt60_estimate_s=mode.rt60_s if math.isfinite(mode.rt60_s) else 0.0,
                eigenvalue_per_m2=mode.eigenvalue_per_m2.real,
                residual=mode.residual,
                shape_2d=shape,
                grid_x=grid_x,
                grid_y=grid_y,
                mesh_nodes=len(mesh.nodes),
                mesh_triangles=len(mesh.elements),
                method=result.method,
                research_status=result.research_status,
            )
        )
    return FEM2DResponse(
        modes=modes,
        width=data.width,
        height=data.height,
        boundary_condition=result.boundary_condition,
        environment=_environment_response(environment),
    )


@router.post(
    "/numerical/fem2d",
    response_model=FEM2DResponse,
    dependencies=[Depends(require_feature("numerical")), Depends(enforce_rate_limit)],
)
async def fem2d_analysis(data: FEM2DRequest) -> FEM2DResponse:
    return _fem_mode_payload(data)


@router.post(
    "/numerical/fem2d/polygon",
    response_model=PolygonFEMResponse,
    dependencies=[Depends(require_feature("research")), Depends(enforce_rate_limit)],
)
async def polygon_fem_analysis(data: PolygonFEMRequest) -> PolygonFEMResponse:
    from acoustic_numerics.fem2d import couple_vertical_modes, solve_polygon_modes

    environment = _core_environment(data.environment)
    boundary_impedance = (
        None
        if data.boundary_impedance_real is None
        else complex(data.boundary_impedance_real, data.boundary_impedance_imag)
    )
    result = solve_polygon_modes(
        data.vertices,
        data.target_edge_length_m,
        num_modes=data.num_modes,
        sound_speed_m_s=environment.sound_speed_m_s,
        density_kg_m3=data.density_kgm3,
        boundary_impedance=boundary_impedance,
    )
    coupled = (
        couple_vertical_modes(
            result.modes,
            data.room_height_m,
            data.max_vertical_order,
            sound_speed_m_s=environment.sound_speed_m_s,
        )
        if data.room_height_m is not None
        else []
    )
    return PolygonFEMResponse(
        nodes=[tuple(float(value) for value in node) for node in result.mesh.nodes],
        elements=[tuple(int(value) for value in element) for element in result.mesh.elements],
        boundary_markers=[int(value) for value in result.mesh.boundary_markers],
        nominal_spacing_m=result.mesh.nominal_spacing_m,
        modes=[
            {
                "mode": mode.mode_index,
                "frequency_hz": mode.frequency_hz,
                "frequency_imag_hz": mode.complex_frequency_hz.imag,
                "decay_rate_neper_s": mode.decay_rate_neper_s,
                "rt60_estimate_s": mode.rt60_s if math.isfinite(mode.rt60_s) else 0.0,
                "eigenvalue_real_per_m2": mode.eigenvalue_per_m2.real,
                "eigenvalue_imag_per_m2": mode.eigenvalue_per_m2.imag,
                "residual": mode.residual,
                "shape_real": [float(value.real) for value in mode.shape],
                "shape_imag": [float(value.imag) for value in mode.shape],
            }
            for mode in result.modes
        ],
        coupled_modes=[
            {
                "horizontal_mode_index": mode.horizontal_mode_index,
                "vertical_order": mode.vertical_order,
                "frequency_hz": mode.frequency_hz,
                "frequency_imag_hz": mode.complex_frequency_hz.imag,
                "decay_rate_neper_s": mode.decay_rate_neper_s,
                "rt60_estimate_s": mode.rt60_s if math.isfinite(mode.rt60_s) else 0.0,
            }
            for mode in coupled
        ],
        method=result.method,
        boundary_condition=result.boundary_condition,
        environment=_environment_response(environment),
        research_status=result.research_status,
    )


def _trace_room(
    room: Room,
    source: tuple[float, float, float],
    receiver: tuple[float, float, float],
    *,
    num_rays: int,
    max_reflections: int,
    max_time_s: float,
    listener_radius_m: float,
    scattering: float,
    seed: int,
    bands_hz: list[float],
) -> dict[str, object]:
    from acoustic_numerics.ray_tracing import (
        BandMaterial,
        RayTraceConfig,
        shoebox_scene,
        trace_scene,
    )

    materials = [
        BandMaterial(absorption=surface.material.alpha, scattering=scattering)
        for surface in room.superficies
    ]
    scene = shoebox_scene(
        (room.largo, room.ancho, room.alto),
        materials=materials,
        surface_ids=[surface.nombre for surface in room.superficies],
    )
    air_absorption = {
        str(frequency): room.environment.air_attenuation_db_per_m(frequency)
        for frequency in bands_hz
    }
    configuration = RayTraceConfig(
        bands_hz=tuple(bands_hz),
        num_rays=num_rays,
        max_reflections=max_reflections,
        max_time_s=max_time_s,
        listener_radius_m=listener_radius_m,
        sound_speed_m_s=room.sound_speed,
        seed=seed,
        air_absorption_db_per_m=air_absorption,
    )
    result = trace_scene(scene, source, receiver, configuration)
    payload = result.to_dict()
    occupied = [
        index
        for index in range(len(result.times_s))
        if any(
            result.energy_by_band[band_index, index] > 0
            for band_index in range(len(result.bands_hz))
        )
    ]
    reference_index = min(
        range(len(result.bands_hz)),
        key=lambda index: abs(float(result.bands_hz[index]) - 500.0),
    )
    payload.update(
        {
            "num_rays": num_rays,
            "energy_time_s": [float(result.times_s[index]) for index in occupied],
            "energy_db": [
                float(result.energy_db_by_band[reference_index, index]) for index in occupied
            ],
            "rt60_estimate_s": float(result.rt60_s_by_band[reference_index]),
            "method": (
                "geometric acoustics with exact segment listener capture and next-event estimation"
            ),
            "environment": _environment_response(room.environment),
        }
    )
    return payload


def _ray_trace_payload(data: RayTraceRequest) -> RayTraceResponse:
    room = _build_room(data)
    result = _trace_room(
        room,
        data.source,
        data.receiver,
        num_rays=data.num_rays,
        max_reflections=data.max_reflections,
        max_time_s=data.max_time_s,
        listener_radius_m=data.listener_radius_m,
        scattering=data.scattering,
        seed=data.seed,
        bands_hz=data.bands_hz,
    )
    return RayTraceResponse(**result)


@router.post(
    "/numerical/ray-tracing",
    response_model=RayTraceResponse,
    dependencies=[Depends(require_feature("numerical")), Depends(enforce_rate_limit)],
)
async def ray_tracing_analysis(data: RayTraceRequest) -> RayTraceResponse:
    return _ray_trace_payload(data)


def _hybrid_payload(data: HybridRequest) -> HybridResponse:
    from acoustic_numerics.hybrid import FrequencyResponse, hybridize_frequency_responses

    room = _build_room(data)
    rt60 = rt60_sabine(
        room,
        "500",
        environment=room.environment,
        include_air_attenuation=True,
        warn=False,
    )
    if not math.isfinite(rt60) or rt60 <= 0:
        rt60 = 0.5
    schroeder = calculate_schroeder(rt60, room.volumen) or 1.0
    image_sources = generate_image_sources(
        room,
        data.source,
        data.receiver,
        max_order=data.max_ism_order,
        c=room.sound_speed,
    )
    energetic_sources = calculate_energy(image_sources, room, bands=BANDAS_OCTAVA)
    low_energy = [
        sum(source["energies_by_band"][band] for source in energetic_sources)
        for band in BANDAS_OCTAVA
    ]
    impulse = build_impulse_response(
        energetic_sources,
        fs=44_100,
        duration_s=0.5,
        banda_energia="500",
        room=room,
    )
    iso_parameters = calculate_iso3382_parameters(
        impulse["impulse_response"],
        44_100,
        impulse["direct_delay_ms"],
        metric_context="predicted_model",
    )
    frequencies = [float(band) for band in BANDAS_OCTAVA]
    ray = _trace_room(
        room,
        data.source,
        data.receiver,
        num_rays=data.num_rays,
        max_reflections=data.max_reflections,
        max_time_s=0.5,
        listener_radius_m=0.15,
        scattering=0.0,
        seed=data.seed,
        bands_hz=frequencies,
    )
    high_energy = [float(ray["total_energy_by_band"].get(band, 0.0)) for band in BANDAS_OCTAVA]
    spectral = hybridize_frequency_responses(
        high_frequency_response=FrequencyResponse(
            frequencies, high_energy, method="ray_tracing", quantity="energy"
        ),
        schroeder_hz=schroeder,
        geometry="shoebox",
        ism_response=FrequencyResponse(
            frequencies, low_energy, method="ism", quantity="energy"
        ),
        frequencies_hz=frequencies,
        crossover_octaves=data.crossover_octaves,
    )
    spectral_payload = spectral.to_dict()
    reference_index = min(
        range(len(frequencies)), key=lambda index: abs(frequencies[index] - 500.0)
    )
    legacy_rt60 = float(ray["rt60_estimate_s"])
    if legacy_rt60 <= 0:
        legacy_rt60 = float(iso_parameters.get("T20") or 0.0)
    payload = {
        "schroeder_frequency_hz": schroeder,
        "modal_count_below_schroeder": len(calculate_modes(room, f_max=schroeder)),
        "ism": {
            "image_sources": len(image_sources),
            "max_order": data.max_ism_order,
            "iso_3382": iso_parameters,
            "frequency_energy": dict(zip(BANDAS_OCTAVA, low_energy)),
        },
        "ray_tracing": {
            "num_rays": data.num_rays,
            "energy_time_s": ray["energy_time_s"],
            "energy_db": ray["energy_db"],
            "rt60_estimate_s": ray["rt60_estimate_s"],
            "frequency_energy": dict(zip(BANDAS_OCTAVA, high_energy)),
            "seed": data.seed,
        },
        "low_frequency": spectral_payload["low_frequency"],
        "high_frequency": spectral_payload["high_frequency"],
        "frequency_response": spectral_payload,
        "hybrid": {
            "rt60_estimate_s": legacy_rt60,
            "rt60_note": "Legacy display value selected from ray T20/ISM T20; it is not blended.",
            "weight_ism": float(spectral.low_weights[reference_index]),
            "weight_ray_tracing": float(spectral.high_weights[reference_index]),
            "frequencies_hz": frequencies,
            "energy": spectral_payload["combined_values"],
        },
        "environment": _environment_response(room.environment),
        "research_status": spectral.research_status,
    }
    return HybridResponse(**payload)


@router.post(
    "/numerical/hybrid",
    response_model=HybridResponse,
    dependencies=[Depends(require_feature("numerical")), Depends(enforce_rate_limit)],
)
async def hybrid_analysis_endpoint(data: HybridRequest) -> HybridResponse:
    return _hybrid_payload(data)


@router.get(
    "/license/status",
    response_model=LicenseStatusResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def license_status(
    principal: AuthenticatedPrincipal = Depends(verify_endpoint_access),
) -> LicenseStatusResponse:
    return LicenseStatusResponse(
        user_id=principal.user_id,
        license_id=principal.license_id,
        api_key_id=principal.api_key_id,
        email=principal.email,
        tier=principal.tier.value,
        key_prefix=principal.key_prefix,
        entitlements=sorted(principal.entitlements),
        quotas=dict(principal.quotas),
    )


def _job_response(view: object) -> JobStatusResponse:
    return JobStatusResponse(
        id=view.id,
        kind=view.kind,
        status=view.status.value,
        result=dict(view.result) if view.result is not None else None,
        error=view.error,
        attempts=view.attempts,
        created_at=view.created_at,
        started_at=view.started_at,
        finished_at=view.finished_at,
    )


@router.post(
    "/jobs",
    response_model=JobStatusResponse,
)
async def submit_job(
    data: JobSubmitRequest,
    request: Request,
    response: Response,
    principal: AuthenticatedPrincipal = Depends(require_feature("jobs")),
    database: Session = Depends(get_db),
    queue: object = Depends(get_job_queue),
    limiter: object = Depends(get_rate_limiter),
) -> JobStatusResponse:
    spec = JOB_KINDS.get(data.kind)
    if spec is None:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported job kind: {data.kind}",
        )
    try:
        validated = spec.schema.model_validate(data.payload)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="Job payload does not match the kind schema",
        ) from exc

    client_ip = request.client.host if request.client else None
    result = limiter.check(
        rate_limit_identity(principal, client_ip),
        principal.tier,
        "/api/v1/jobs",
        cost=spec.cost,
        quota_overrides=principal.quotas,
    )
    result.raise_if_limited()
    response.headers.update(result.headers)

    limit = int(principal.quotas.get("max_concurrent_jobs", 1))
    if active_job_count(database, principal) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Job concurrency quota exceeded for this license",
        )

    job = enqueue_job(
        database,
        queue,
        data.kind,
        validated.model_dump(mode="json"),
        principal=principal,
        idempotency_key=data.idempotency_key,
        max_attempts=data.max_attempts,
    )
    view = get_job_status(database, job.id, principal=principal)
    if view is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(view)


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def job_status(
    job_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("jobs")),
    database: Session = Depends(get_db),
) -> JobStatusResponse:
    view = get_job_status(database, job_id, principal=principal)
    if view is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(view)


@router.delete(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def cancel_job_endpoint(
    job_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("jobs")),
    database: Session = Depends(get_db),
) -> JobStatusResponse:
    view = get_job_status(database, job_id, principal=principal)
    if view is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if view.status.value != "QUEUED":
        raise HTTPException(status_code=409, detail="Only queued jobs can be cancelled")
    if not cancel_job(database, job_id, principal=principal):
        raise HTTPException(status_code=409, detail="Job could not be cancelled")
    updated = get_job_status(database, job_id, principal=principal)
    if updated is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(updated)


def _asset_response(asset: object) -> StoredAssetResponse:
    return StoredAssetResponse.model_validate(asset)


@router.post(
    "/objects",
    response_model=StoredAssetResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
async def upload_object(
    file: UploadFile = File(...),
    category: str = Form(default="upload"),
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> StoredAssetResponse:
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    await file.close()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Object upload exceeds {MAX_UPLOAD_BYTES} bytes",
        )
    if category not in {"upload", "wav", "export"}:
        raise HTTPException(status_code=422, detail="Unsupported object category")
    try:
        asset = create_asset(
            database,
            storage,
            principal,
            filename=file.filename,
            content_type=file.content_type,
            data=data,
            category=category,
        )
    except StorageQuotaExceeded as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return _asset_response(asset)


@router.get(
    "/objects",
    response_model=StoredAssetListResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def stored_objects(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
) -> StoredAssetListResponse:
    items, total = list_assets(database, principal, offset=offset, limit=limit)
    return StoredAssetListResponse(
        items=[_asset_response(item) for item in items],
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get(
    "/objects/usage",
    response_model=StorageUsageResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def object_storage_usage(
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
) -> StorageUsageResponse:
    usage = storage_usage(database, principal)
    return StorageUsageResponse(
        used_bytes=usage.used_bytes,
        limit_bytes=usage.limit_bytes,
        remaining_bytes=usage.remaining_bytes,
        object_count=usage.object_count,
        usage_percent=usage.usage_percent,
    )


@router.post(
    "/objects/uploads",
    response_model=MultipartUploadResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
async def initiate_multipart_upload(
    data: MultipartUploadRequest,
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> MultipartUploadResponse:
    try:
        asset, part_size, urls = reserve_multipart_asset(
            database,
            storage,
            principal,
            filename=data.filename,
            content_type=data.content_type,
            size_bytes=data.size_bytes,
            sha256=data.sha256,
            category=data.category,
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=409, detail="Multipart uploads require S3") from exc
    except StorageQuotaExceeded as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    return MultipartUploadResponse(
        asset_id=asset.id,
        part_size_bytes=part_size,
        upload_urls=urls,
        expires_in_seconds=3600,
    )


@router.post(
    "/objects/uploads/{asset_id}/complete",
    response_model=StoredAssetResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def complete_multipart_upload(
    asset_id: UUID,
    data: MultipartCompleteRequest,
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> StoredAssetResponse:
    parts = [
        {"PartNumber": part.part_number, "ETag": part.etag}
        for part in data.parts
    ]
    try:
        return _asset_response(
            complete_multipart_asset(database, storage, principal, asset_id, parts)
        )
    except StoredAssetNotFound as exc:
        raise HTTPException(status_code=404, detail="Multipart upload not found") from exc
    except AssetIntegrityError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/objects/{asset_id}",
    response_model=StoredAssetResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def stored_object_metadata(
    asset_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
) -> StoredAssetResponse:
    try:
        return _asset_response(get_asset(database, principal, asset_id))
    except StoredAssetNotFound as exc:
        raise HTTPException(status_code=404, detail="Object not found") from exc


@router.get(
    "/objects/{asset_id}/download",
    response_class=Response,
    dependencies=[Depends(enforce_rate_limit)],
)
async def download_stored_object(
    asset_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    try:
        asset, data = read_asset(database, storage, principal, asset_id)
    except StoredAssetNotFound as exc:
        raise HTTPException(status_code=404, detail="Object not found") from exc
    except AssetIntegrityError as exc:
        raise HTTPException(status_code=409, detail="Object integrity check failed") from exc
    filename = quote(asset.filename, safe="")
    return Response(
        content=data,
        media_type=asset.content_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.delete(
    "/objects/{asset_id}",
    status_code=204,
    dependencies=[Depends(enforce_rate_limit)],
)
async def delete_stored_object(
    asset_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("storage")),
    database: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> Response:
    try:
        delete_asset(database, storage, principal, asset_id)
    except StoredAssetNotFound as exc:
        raise HTTPException(status_code=404, detail="Object not found") from exc
    return Response(status_code=204)


@router.get(
    "/storage/metrics",
    response_model=StorageMetricsResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def storage_metrics_endpoint(
    principal: AuthenticatedPrincipal = Depends(require_feature("research")),
    database: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage),
) -> StorageMetricsResponse:
    del principal
    metrics = storage_metrics(database)
    try:
        storage.list_keys("")
        available = True
    except Exception:
        available = False
    return StorageMetricsResponse(**metrics, backend_available=available)


def _project_response(project: object) -> ProjectResponse:
    return ProjectResponse.model_validate(project)


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_project_endpoint(
    data: ProjectCreateRequest,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> ProjectResponse:
    return _project_response(create_project(database, principal, data.name, data.description))


@router.get(
    "/projects",
    response_model=list[ProjectResponse],
    dependencies=[Depends(enforce_rate_limit)],
)
async def projects_endpoint(
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> list[ProjectResponse]:
    return [_project_response(project) for project in list_projects(database, principal)]


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def project_endpoint(
    project_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        return _project_response(get_project(database, principal, project_id))
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def update_project_endpoint(
    project_id: UUID,
    data: ProjectUpdateRequest,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> ProjectResponse:
    try:
        project = get_project(database, principal, project_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    if data.name is not None:
        project.name = data.name.strip()
    if "description" in data.model_fields_set:
        project.description = data.description
    if data.archived is not None:
        project.archived = data.archived
    database.commit()
    return _project_response(project)


@router.delete(
    "/projects/{project_id}",
    status_code=204,
    dependencies=[Depends(enforce_rate_limit)],
)
async def delete_project_endpoint(
    project_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> Response:
    try:
        project = get_project(database, principal, project_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    database.delete(project)
    database.commit()
    return Response(status_code=204)


@router.post(
    "/projects/{project_id}/calculations",
    response_model=CalculationResponse,
    status_code=201,
    dependencies=[Depends(enforce_rate_limit)],
)
async def create_calculation_endpoint(
    project_id: UUID,
    data: CalculationCreateRequest,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> CalculationResponse:
    try:
        get_project(database, principal, project_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    calculation = Calculation(project_id=project_id, **data.model_dump())
    database.add(calculation)
    database.commit()
    return CalculationResponse.model_validate(calculation)


@router.get(
    "/projects/{project_id}/calculations",
    response_model=list[CalculationResponse],
    dependencies=[Depends(enforce_rate_limit)],
)
async def project_calculations_endpoint(
    project_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> list[CalculationResponse]:
    try:
        get_project(database, principal, project_id)
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc
    calculations = database.query(Calculation).filter_by(project_id=project_id).all()
    return [CalculationResponse.model_validate(item) for item in calculations]


@router.post(
    "/projects/{project_id}/objects/{asset_id}",
    response_model=StoredAssetResponse,
    dependencies=[Depends(enforce_rate_limit)],
)
async def attach_project_object_endpoint(
    project_id: UUID,
    asset_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> StoredAssetResponse:
    try:
        return _asset_response(attach_asset(database, principal, project_id, asset_id))
    except (ProjectNotFound, StoredAssetNotFound) as exc:
        raise HTTPException(status_code=404, detail="Project or object not found") from exc


@router.get(
    "/projects/{project_id}/objects",
    response_model=list[StoredAssetResponse],
    dependencies=[Depends(enforce_rate_limit)],
)
async def project_objects_endpoint(
    project_id: UUID,
    principal: AuthenticatedPrincipal = Depends(require_feature("projects")),
    database: Session = Depends(get_db),
) -> list[StoredAssetResponse]:
    try:
        return [_asset_response(item) for item in project_assets(database, principal, project_id)]
    except ProjectNotFound as exc:
        raise HTTPException(status_code=404, detail="Project not found") from exc

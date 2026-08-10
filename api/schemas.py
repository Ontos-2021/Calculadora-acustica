from __future__ import annotations

import math
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from acoustic_core.isolation import (
    ISO717_BANDS_HZ,
    NC_FREQS,
    NR_FREQS,
    STC_BANDS_HZ,
    THIRD_OCTAVE_BANDS_HZ,
)
from acoustic_core.models import BANDAS_OCTAVA


ROOM_BANDS = tuple(BANDAS_OCTAVA)
ROOM_BAND_SET = frozenset(ROOM_BANDS)
MAX_SIGNAL_SAMPLES = 200_000
MAX_SPECTROGRAM_SAMPLES = 65_536
MAX_UPLOAD_BYTES = 16 * 1024 * 1024
MAX_WAV_FRAMES = 1_000_000

PositiveFinite = Annotated[float, Field(gt=0)]
UnitInterval = Annotated[float, Field(ge=0, le=1)]
ModeIndex = Annotated[int, Field(strict=True, ge=0, le=1000)]
Point2D = tuple[float, float]
Point3D = tuple[float, float, float]


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class APIResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, from_attributes=True)


def _band_key(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{float(value):g}"


def _normalize_curve(
    curve: dict[str, float],
    accepted_sets: tuple[frozenset[str], ...],
    label: str,
) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for raw_frequency, value in curve.items():
        try:
            frequency = float(raw_frequency)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} band keys must be numeric frequencies") from exc
        if not math.isfinite(frequency) or frequency <= 0:
            raise ValueError(f"{label} band keys must be positive finite frequencies")
        key = _band_key(frequency)
        if key in normalized:
            raise ValueError(f"duplicate {label} band near {key} Hz")
        normalized[key] = value
    actual = frozenset(normalized)
    if actual not in accepted_sets:
        expected = " or ".join(
            "{" + ", ".join(sorted(bands, key=float)) + "}" for bands in accepted_sets
        )
        raise ValueError(f"{label} must contain exactly the bands {expected}")
    return normalized


class EnvironmentRequest(APIModel):
    temperature_c: float = Field(default=20.0, gt=-273.15, le=100.0)
    relative_humidity: float = Field(default=50.0, ge=0.0, le=100.0)
    pressure_pa: float = Field(default=101_325.0, gt=0.0, le=2_000_000.0)


class EnvironmentResponse(APIResponseModel):
    temperature_c: float
    relative_humidity: float
    pressure_pa: float
    sound_speed_m_s: float


class SurfaceRequest(APIModel):
    material: str = Field(default="Concreto", min_length=1, max_length=200)
    alphas: dict[str, UnitInterval] | None = Field(
        default=None,
        min_length=1,
        max_length=len(ROOM_BANDS),
        description=(
            "Absorption overrides keyed by 125, 250, 500, 1000, 2000, and 4000 Hz. "
            "Partial values are merged with a known material preset; a custom material "
            "must provide all six bands."
        ),
    )

    @field_validator("material")
    @classmethod
    def strip_material(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("material must not be blank")
        return value

    @field_validator("alphas")
    @classmethod
    def validate_alpha_bands(
        cls, value: dict[str, float] | None
    ) -> dict[str, float] | None:
        if value is None:
            return None
        unknown = sorted(set(value) - ROOM_BAND_SET, key=str)
        if unknown:
            raise ValueError(f"unknown absorption bands: {', '.join(unknown)}")
        return value


def _default_surfaces() -> list[SurfaceRequest]:
    return [SurfaceRequest() for _ in range(6)]


class RoomRequest(APIModel):
    largo: float = Field(gt=0, le=1000)
    ancho: float = Field(gt=0, le=1000)
    alto: float = Field(gt=0, le=1000)
    superficies: list[SurfaceRequest] = Field(
        default_factory=_default_surfaces, min_length=6, max_length=6
    )
    environment: EnvironmentRequest = Field(default_factory=EnvironmentRequest)


class CalculateRequest(RoomRequest):
    uso: str | None = Field(default=None, min_length=1, max_length=100)
    include_air_attenuation: bool = False


class ModeSchema(APIResponseModel):
    indices: tuple[int, int, int]
    frecuencia: float
    tipo: Literal["axial", "tangencial", "oblicuo"]
    peso_db: float
    degenerado: bool = False
    solapado: bool = False
    multiplicity: int = 1
    degeneracy_cluster: int | None = None
    overlap_multiplicity: int = 1
    overlap_cluster: int | None = None


class BonelloSchema(APIResponseModel):
    cumple: bool
    bandas: dict[float, int]
    violaciones: list[int]
    total_modos: int


class ProporcionSchema(APIResponseModel):
    proporcion_actual: tuple[float, float, float]
    mas_cercana: str
    proporcion_cercana: tuple[float, float, float]
    error: float
    todas: list[tuple[str, float, float]]
    en_area_bolt: bool
    distancia_area_bolt: float
    proporcion_bolt_mas_cercana: tuple[float, float, float]
    convencion_dimensiones: str
    multiplos_enteros: list[tuple[str, str, int]]


class ObjetivoSchema(APIResponseModel):
    label: str
    valores: dict[str, float]
    diferencias: dict[str, float] | None = None


class RT60BandSchema(APIResponseModel):
    sabine: float = Field(alias="Sabine")
    eyring: float = Field(alias="Eyring")
    millington: float = Field(alias="Millington")
    fitzroy: float = Field(alias="FitzRoy")

    model_config = ConfigDict(
        extra="forbid", allow_inf_nan=False, from_attributes=True, populate_by_name=True
    )


class MethodWarningSchema(APIResponseModel):
    code: str
    message: str
    method: str | None = None
    band_hz: str | None = None
    surface: str | None = None
    severity: Literal["info", "warning"] = "warning"


class DiffuseFieldSchema(APIResponseModel):
    campo_difuso: bool
    umbral_solapamiento: int
    solapamiento_maximo: int
    clusters_difusos: list[int]
    is_diffuse: bool
    minimum_overlap: int
    max_overlap: int


class BoltAreaSchema(APIResponseModel):
    normalized_ratio: tuple[float, float, float]
    is_inside: bool
    distance: float
    nearest_ratio: tuple[float, float, float]
    dimension_convention: str


class CalculateResponse(APIResponseModel):
    modos: list[ModeSchema]
    frecuencias: list[float]
    cantidad_modos: int
    distribucion: dict[str, int | bool]
    rt60_bandas: dict[str, RT60BandSchema]
    rt60_promedio: float
    f_schroeder: float
    delta_f: float
    bonello: BonelloSchema
    proporciones: ProporcionSchema
    degeneracion_dimensiones: list[str]
    objetivo: ObjetivoSchema | None = None
    method_warnings: list[MethodWarningSchema] = Field(default_factory=list)
    environment: EnvironmentResponse
    sound_speed_m_s: float
    diffuse_field: DiffuseFieldSchema
    bolt_area: BoltAreaSchema


class PressureMapRequest(RoomRequest):
    ear_height: float = Field(default=1.2, ge=0)
    max_freq: float = Field(default=300.0, gt=0, le=1000)
    grid_size: int = Field(default=100, ge=10, le=200)
    mode_indices: tuple[ModeIndex, ModeIndex, ModeIndex] | None = None

    @model_validator(mode="after")
    def validate_pressure_request(self) -> "PressureMapRequest":
        if self.ear_height > self.alto:
            raise ValueError("ear_height must be inside the room")
        if self.mode_indices is not None:
            if any(index < 0 for index in self.mode_indices):
                raise ValueError("mode_indices must be non-negative")
            if self.mode_indices == (0, 0, 0):
                raise ValueError("mode_indices (0, 0, 0) is not a physical mode")
        estimated_modes = (
            4.0
            * math.pi
            * self.largo
            * self.ancho
            * self.alto
            * self.max_freq**3
            / (3.0 * 330.0**3)
        )
        if self.mode_indices is None and estimated_modes * self.grid_size**2 > 25_000_000:
            raise ValueError("pressure-map frequency/grid combination exceeds the compute bound")
        return self


class ListeningPositionSchema(APIResponseModel):
    x: float
    y: float
    score: float
    score_unit: str
    boundary_margin: float
    reference_position: dict[str, float]
    reference_score_db: float
    movement_m: float
    movement: dict[str, float]
    improvement_db: float
    db_improvement: float
    warnings: list[str] = Field(default_factory=list)


class PressureMapResponse(APIResponseModel):
    grid_x: list[float]
    grid_y: list[float]
    pressure: list[list[float]]
    magnitude: list[list[float]]
    energy: list[list[float]] | None = None
    signed_pressure: list[list[float]] | None = None
    quantity: str
    max_freq: float
    ear_height: float
    num_modos: int
    optimal_listening: ListeningPositionSchema
    warnings: list[str] = Field(default_factory=list)
    environment: EnvironmentResponse


class SourceReceiverRoomRequest(RoomRequest):
    source: Point3D = (1.0, 1.0, 1.5)
    receiver: Point3D = (4.0, 3.0, 1.2)

    @model_validator(mode="after")
    def validate_source_receiver(self) -> "SourceReceiverRoomRequest":
        dimensions = (self.largo, self.ancho, self.alto)
        for label, point in (("source", self.source), ("receiver", self.receiver)):
            if any(not 0.0 < coordinate < dimension for coordinate, dimension in zip(point, dimensions)):
                raise ValueError(f"{label} must be strictly inside the room")
        if self.source == self.receiver:
            raise ValueError("source and receiver must not be coincident")
        return self


class IRRequest(SourceReceiverRoomRequest):
    max_order: int = Field(default=8, ge=0, le=15)
    sample_rate: int = Field(default=44100, ge=8000, le=96000)
    duration_s: float = Field(default=1.0, gt=0, le=5)
    band: Literal["125", "250", "500", "1000", "2000", "4000"] = "500"
    normalize: bool = False

    @model_validator(mode="after")
    def validate_ir_size(self) -> "IRRequest":
        if round(self.sample_rate * self.duration_s) > MAX_SIGNAL_SAMPLES:
            raise ValueError("impulse response exceeds the API sample bound")
        return self


class RegressionDiagnosticSchema(APIResponseModel):
    range_db: tuple[float, float]
    valid_dynamic_range_db: float
    sample_count: int
    slope_db_per_s: float | None
    intercept_db: float | None
    r2: float | None
    residual_rms_db: float | None
    max_residual_db: float | None
    nonlinearity_percent: float | None
    is_nonlinear: bool | None
    rt60_s: float | None
    valid: bool
    reason: str | None = None


class FlutterEchoSchema(APIResponseModel):
    detected: bool
    frequency: float | None
    period_ms: float | None
    correlation: float
    polarity: str | None
    threshold: float
    reason: str | None
    median_sidelobe: float | None = None
    analysis_sample_rate: float | None = None


class ISOScalarMetricsSchema(APIResponseModel):
    EDT: float | None
    T20: float | None
    T30: float | None
    C80: float
    C50: float
    D50: float
    Ts: float
    ITDG: float | None


class ISO3382ParametersSchema(ISOScalarMetricsSchema):
    flutter_echo: FlutterEchoSchema
    regression_diagnostics: dict[str, RegressionDiagnosticSchema]
    valid_dynamic_range_db: float
    direct_arrival_ms: float
    direct_arrival_sample: int
    metric_context: str
    predicted_model_metrics: ISOScalarMetricsSchema | None
    method: str
    energy_ratio_floor_db: float


class MeasurementErrorSchema(APIResponseModel):
    error: str


class IRResponse(APIResponseModel):
    impulse_response: list[float]
    sample_rate: int
    direct_delay_ms: float
    direct_delay_s: float
    direct_sample: float
    arrivals_rendered: int
    image_source_count: int
    impulse_representation: str
    normalization_gain: float
    band: str
    parameters: ISO3382ParametersSchema | MeasurementErrorSchema
    environment: EnvironmentResponse


class HealthResponse(APIResponseModel):
    status: str = "ok"
    version: str = "1.0"
    core_version: str = "0.1"


class CoreBundleResponse(RootModel[dict[str, str]]):
    pass


class UncertaintySchema(APIResponseModel):
    standard: float
    expanded: float
    unit: str
    coverage_factor: float
    confidence_level: float | None
    source: str | None


class ISO11654Response(APIResponseModel):
    alpha_w: float
    iso_class: str
    practical_coefficients: dict[str, float]
    shifted_reference_curve: dict[str, float]
    unfavorable_deviations: dict[str, float]
    unfavorable_deviation_sum: float
    shape_indicators: list[str]
    designation: str
    inferred_bands: list[str]
    implementation_note: str


class MaterialCatalogMetadataSchema(APIResponseModel):
    name: str
    category: str
    mounting_condition: str
    coefficient_basis: str
    data_status: str
    provenance: str
    uncertainty: UncertaintySchema
    thickness_m: float | None
    alias_of: str | None
    references: list[str]


class MaterialResponse(APIResponseModel):
    nombre: str
    categoria: str
    alphas: dict[str, float]
    alpha_w: float | None = None
    iso_class: str
    provenance: str | None = None
    uncertainty: UncertaintySchema | None = None
    catalog: MaterialCatalogMetadataSchema | None = None
    iso11654: ISO11654Response | None = None


class MaterialClassificationRequest(APIModel):
    practical_coefficients: dict[str, UnitInterval] = Field(min_length=5, max_length=5)

    @field_validator("practical_coefficients")
    @classmethod
    def validate_iso_bands(cls, value: dict[str, float]) -> dict[str, float]:
        expected = frozenset({"250", "500", "1000", "2000", "4000"})
        return _normalize_curve(value, (expected,), "ISO 11654 practical coefficients")


class MaterialCategoriesResponse(RootModel[dict[str, list[str]]]):
    pass


class DesignRatiosResponse(RootModel[dict[str, tuple[float, float, float]]]):
    pass


class DesignTargetsResponse(RootModel[dict[str, ObjetivoSchema]]):
    pass


class AirAbsorptionRequest(APIModel):
    humidity: float = Field(default=50.0, ge=0, le=100)
    temp_celsius: float = Field(default=20.0, gt=-273.15, le=100)
    pressure_pa: float = Field(default=101_325.0, gt=0, le=2_000_000)


class AirAbsorptionResponse(APIResponseModel):
    coeficientes: dict[str, float]
    attenuation_db_per_m: dict[str, float]
    humidity: float
    temp_celsius: float
    pressure_pa: float
    sound_speed_m_s: float


class AudienceAbsorptionRequest(APIModel):
    num_people: int = Field(default=0, ge=0, le=1_000_000)
    seated: bool = True
    upholstered: bool = True
    occupied: float = Field(default=0.85, ge=0, le=1)


class BandValuesResponse(RootModel[dict[str, float]]):
    pass


class AudienceAbsorptionDetailsResponse(APIResponseModel):
    equivalent_absorption_area_m2_sabins: dict[str, float]
    occupied_people_equivalent: float
    empty_seats_equivalent: float
    occupied_absorption_per_person_m2: dict[str, float]
    empty_seat_absorption_m2: dict[str, float]
    assumptions: list[str]
    estimate_label: str


class InverseDesignRequest(RoomRequest):
    target_uso: str = Field(min_length=1, max_length=100)
    include_placement: bool = False


class MaterialSuggestion(APIResponseModel):
    material: str
    area_needed_m2: float
    alpha_w: float | None = None
    iso_class: str
    categoria: str
    per_band: dict[str, float]
    installation_mode: str | None = None
    available_area_m2: float | None = None
    feasible: bool | None = None
    governing_bands: list[str] = Field(default_factory=list)
    predicted_rt60_s: dict[str, float | None] | None = None
    estimate_label: str | None = None


class PlacementSuggestion(APIResponseModel):
    surface: str
    surface_area_m2: float
    missing_absorption_m2: float
    priority_score: float
    coverage_percent: float
    room_surface_name: str | None = None
    surface_index: int | None = None
    available_area_m2: float | None = None
    missing_absorption_by_band_m2_sabins: dict[str, float] | None = None
    governing_band: str | None = None
    pressure_evidence_score: float | None = None
    pressure_evidence: str | None = None
    aggregation_rule: str | None = None


class InverseDesignResponse(APIResponseModel):
    current_absorption: dict[str, float]
    required_absorption: dict[str, float]
    missing_absorption: dict[str, float]
    material_suggestions: list[MaterialSuggestion]
    placement_suggestions: list[PlacementSuggestion] = Field(default_factory=list)


class TreatmentInput(APIModel):
    material: str = Field(min_length=1, max_length=200)
    area_m2: float = Field(ge=0, le=1_000_000)
    surface_index: int | None = Field(default=None, ge=0, le=5)
    installation_mode: Literal["added", "replacement"] = "replacement"

    @model_validator(mode="after")
    def validate_replacement_surface(self) -> "TreatmentInput":
        if self.installation_mode == "replacement" and self.surface_index is None:
            raise ValueError("replacement treatment requires surface_index")
        return self


class TreatmentVerificationRequest(RoomRequest):
    target_rt60: dict[str, PositiveFinite] = Field(
        min_length=len(ROOM_BANDS), max_length=len(ROOM_BANDS)
    )
    treatments: list[TreatmentInput] = Field(default_factory=list, max_length=100)

    @field_validator("target_rt60")
    @classmethod
    def validate_target_bands(cls, value: dict[str, float]) -> dict[str, float]:
        return _normalize_curve(value, (ROOM_BAND_SET,), "target RT60")


class NormalizedTreatmentSchema(APIResponseModel):
    material: str
    area_m2: float
    installation_mode: str
    surface_index: int | None
    surface: str | None
    absorption_gain_m2_sabins: dict[str, float]


class TreatmentVerificationResponse(APIResponseModel):
    treatments: list[NormalizedTreatmentSchema]
    current_absorption_m2_sabins: dict[str, float]
    predicted_absorption_m2_sabins: dict[str, float]
    required_absorption_m2_sabins: dict[str, float]
    remaining_missing_absorption_m2_sabins: dict[str, float]
    predicted_rt60_s: dict[str, float | None]
    target_rt60_s: dict[str, float]
    meets_target_by_band: dict[str, bool]
    all_bands_meet: bool
    aggregation_rule: str
    estimate_label: str


class TreatmentOptimizationRequest(RoomRequest):
    target_uso: str = Field(min_length=1, max_length=100)
    candidate_materials: list[str] | None = Field(default=None, min_length=1, max_length=20)
    available_area_m2: float | None = Field(default=None, ge=0, le=1_000_000)
    installation_mode: Literal["added", "replacement"] = "replacement"
    max_materials: int = Field(default=3, ge=1, le=20)
    area_step_m2: float = Field(default=0.25, gt=0, le=1000)
    include_pressure_map: bool = False


class TreatmentOptimizationResponse(APIResponseModel):
    status: str
    installation_mode: str
    allocations: list[NormalizedTreatmentSchema]
    selected_materials: list[str] = Field(default_factory=list)
    available_area_m2: float
    available_area_by_surface_m2: dict[str, float] = Field(default_factory=dict)
    used_area_m2: float
    area_step_m2: float | None = None
    optimization_method: str
    pressure_evidence: str
    forward_verification: TreatmentVerificationResponse
    predicted_rt60_s: dict[str, float | None]
    all_bands_meet: bool
    estimate_label: str
    target_uso: str
    target_label: str


class PorousAbsorberRequest(APIModel):
    thickness_m: float = Field(default=0.05, gt=0, le=1)
    flow_resistivity: float = Field(default=10000, gt=0, le=1_000_000)
    density_kgm3: float | None = Field(default=100, gt=0, le=1000)
    air_gap_m: float = Field(default=0, ge=0, le=10)
    incidence_angle_deg: float = Field(default=0, ge=0, lt=90)
    strict_validity: bool = False
    air_density_kgm3: float = Field(default=1.2, gt=0, le=100)
    environment: EnvironmentRequest = Field(default_factory=EnvironmentRequest)


class HelmholtzRequest(APIModel):
    neck_area_m2: float | None = Field(default=0.01, gt=0, le=1)
    cavity_volume_m3: float = Field(default=0.1, gt=0, le=10)
    neck_length_m: float = Field(default=0.05, ge=0, le=1)
    neck_radius_m: float | None = Field(default=0.02, gt=0, le=0.5)
    panel_area_m2: float | None = Field(default=None, gt=0, le=10_000)
    open_area_ratio: float | None = Field(default=None, gt=0, le=1)
    hole_count: int | None = Field(default=None, ge=1, le=1_000_000)
    end_correction_coefficient: float = Field(default=1.7, ge=0, le=10)
    quality_factor: float | None = Field(default=None, gt=0, le=10_000)
    loss_factor: float | None = Field(default=None, gt=0, le=1)
    peak_absorption: float = Field(default=1, ge=0, le=1)
    environment: EnvironmentRequest = Field(default_factory=EnvironmentRequest)

    @model_validator(mode="after")
    def validate_helmholtz_options(self) -> "HelmholtzRequest":
        if (self.panel_area_m2 is None) != (self.open_area_ratio is None):
            raise ValueError("panel_area_m2 and open_area_ratio must be supplied together")
        if self.quality_factor is not None and self.loss_factor is not None:
            raise ValueError("specify quality_factor or loss_factor, not both")
        if (
            self.neck_area_m2 is None
            and self.panel_area_m2 is None
            and (self.neck_radius_m is None or self.hole_count is None)
        ):
            raise ValueError(
                "provide neck_area_m2, panel open-area data, or neck_radius_m plus hole_count"
            )
        return self


class MembraneRequest(APIModel):
    mass_per_area_kgm2: float = Field(default=10, gt=0, le=200)
    air_gap_m: float = Field(default=0.1, gt=0, le=2)
    quality_factor: float | None = Field(default=None, gt=0, le=10_000)
    loss_factor: float | None = Field(default=None, gt=0, le=1)
    surface_tension_n_m: float = Field(default=0, ge=0, le=1e9)
    panel_span_m: float | None = Field(default=None, gt=0, le=1000)
    peak_absorption: float = Field(default=0.9, ge=0, le=1)

    @model_validator(mode="after")
    def validate_membrane_options(self) -> "MembraneRequest":
        if self.quality_factor is not None and self.loss_factor is not None:
            raise ValueError("specify quality_factor or loss_factor, not both")
        if self.surface_tension_n_m > 0 and self.panel_span_m is None:
            raise ValueError("panel_span_m is required when surface tension is used")
        return self


class AbsorberResponse(APIResponseModel):
    f0: float
    Q: float = 0
    alpha: dict[str, float]


class PorousAbsorberResponse(APIResponseModel):
    model: str
    alpha: dict[str, float]
    quarter_wave_frequency_hz: float
    quarter_wave_effective_depth_m: float
    air_gap_m: float
    incidence_angle_deg: float
    flow_resistivity_pa_s_m2: float
    density_input_kgm3: float | None
    density_input_used: bool
    validity_parameter_rho_f_over_sigma: dict[str, float]
    valid_by_band: dict[str, bool]
    outside_validity_bands: list[str]
    valid_for_all_bands: bool
    assumptions: list[str]
    reference: str
    estimate_label: str
    environment: EnvironmentResponse


class HelmholtzResponse(APIResponseModel):
    model: str
    f0: float
    alpha: dict[str, float]
    Q: float
    peak_absorption: float
    neck_area_m2: float
    neck_radius_m: float
    effective_hole_count: float
    hole_count: int | None
    panel_area_m2: float | None
    open_area_ratio: float | None
    neck_length_m: float
    end_correction_m: float
    end_correction_coefficient: float
    effective_neck_length_m: float
    loss_model: str
    assumptions: list[str]
    estimate_label: str
    environment: EnvironmentResponse


class MembraneResponse(APIResponseModel):
    model: str
    f0: float
    air_spring_f0_hz: float
    tension_f0_hz: float
    alpha: dict[str, float]
    Q: float
    peak_absorption: float
    surface_tension_n_m: float
    panel_span_m: float | None
    loss_model: str
    assumptions: list[str]
    estimate_label: str


class AbsorberAreaRequest(APIModel):
    absorption_coefficients: dict[str, UnitInterval] = Field(
        min_length=len(ROOM_BANDS), max_length=len(ROOM_BANDS)
    )
    missing_absorption_m2_sabins: dict[str, float] = Field(
        min_length=len(ROOM_BANDS), max_length=len(ROOM_BANDS)
    )
    existing_surface_alpha: dict[str, UnitInterval] | None = Field(
        default=None, min_length=len(ROOM_BANDS), max_length=len(ROOM_BANDS)
    )
    installation_mode: Literal["added", "replacement"] = "added"
    available_area_m2: float | None = Field(default=None, ge=0, le=1_000_000)

    @model_validator(mode="after")
    def validate_absorber_spectra(self) -> "AbsorberAreaRequest":
        self.absorption_coefficients = _normalize_curve(
            self.absorption_coefficients, (ROOM_BAND_SET,), "absorber alpha"
        )
        self.missing_absorption_m2_sabins = _normalize_curve(
            self.missing_absorption_m2_sabins, (ROOM_BAND_SET,), "missing absorption"
        )
        if any(value < 0 for value in self.missing_absorption_m2_sabins.values()):
            raise ValueError("missing absorption must be non-negative")
        if self.existing_surface_alpha is not None:
            self.existing_surface_alpha = _normalize_curve(
                self.existing_surface_alpha, (ROOM_BAND_SET,), "existing surface alpha"
            )
        return self


class AbsorberAreaResponse(APIResponseModel):
    recommended_area_m2: float | None
    available_area_m2: float | None
    feasible: bool
    installation_mode: str
    effective_absorption_coefficients: dict[str, float]
    per_band_area_m2: dict[str, float | None]
    governing_bands: list[str]
    impossible_bands: list[str]
    remaining_missing_absorption_m2_sabins: dict[str, float]
    constraint_rule: str
    estimate_label: str


class QRDRequest(APIModel):
    design_freq_hz: float = Field(default=1000, gt=0, le=10000)
    prime_n: int = Field(default=17, ge=5, le=200)
    well_width_m: float = Field(default=0.05, gt=0, le=1)


class ManufacturabilitySchema(APIResponseModel):
    manufacturable: bool
    minimum_cell_width_m: float
    maximum_depth_to_width_ratio: float
    actual_depth_to_width_ratio: float
    maximum_width_for_design_frequency_m: float
    warnings: list[str]
    limits_are: str


class QRDResponse(APIResponseModel):
    type: Literal["QRD"]
    requested_prime_n: int
    prime_n: int
    design_freq_hz: float
    well_width_m: float
    total_width_m: float
    max_depth_m: float
    actual_max_well_depth_m: float
    lower_useful_frequency_hz: float
    upper_useful_frequency_hz: float
    min_effective_freq_hz: float
    useful_frequency_range_valid: bool
    well_depths_m: list[float]
    sequence: list[int]
    construction: str
    manufacturability: ManufacturabilitySchema
    reference: str
    estimate_label: str
    diffusion_coefficient: dict[str, float]


class SkylineRequest(APIModel):
    design_freq_hz: float = Field(default=1000, gt=0, le=10000)
    grid_n: int = Field(default=7, ge=2, le=20)
    well_size_m: float = Field(default=0.05, gt=0, le=1)


class SkylineResponse(APIResponseModel):
    type: Literal["Skyline"]
    requested_grid_n: int
    grid_n: int
    modulus_prime: int
    design_freq_hz: float
    well_size_m: float
    total_width_m: float
    max_depth_m: float
    actual_max_well_depth_m: float
    lower_useful_frequency_hz: float
    upper_useful_frequency_hz: float
    min_effective_freq_hz: float
    useful_frequency_range_valid: bool
    well_depths_m: list[list[float]]
    sequence_2d: list[list[int]]
    construction: str
    manufacturability: ManufacturabilitySchema
    reference: str
    estimate_label: str


class DiffusionCoefficientRequest(APIModel):
    polar_response: list[float] = Field(min_length=2, max_length=721)
    reference_response: list[float] | None = Field(default=None, min_length=2, max_length=721)
    response_unit: Literal["pressure", "energy", "db"] = "pressure"

    @model_validator(mode="after")
    def validate_reference_length(self) -> "DiffusionCoefficientRequest":
        if (
            self.reference_response is not None
            and len(self.reference_response) != len(self.polar_response)
        ):
            raise ValueError("reference_response must match polar_response length")
        return self


class DiffusionCoefficientResponse(APIResponseModel):
    sample_diffusion_coefficient: float
    reference_diffusion_coefficient: float | None
    normalized_diffusion_coefficient: float
    response_unit: str
    formula: str
    normalization: str
    implementation_note: str
    estimate_label: str


class QRDPolarRequest(APIModel):
    well_depths_m: list[float] = Field(min_length=2, max_length=200)
    frequency_hz: float = Field(gt=0, le=100_000)
    well_width_m: float = Field(gt=0, le=10)
    angles_deg: list[float] | None = Field(default=None, min_length=2, max_length=721)
    environment: EnvironmentRequest = Field(default_factory=EnvironmentRequest)

    @model_validator(mode="after")
    def validate_polar_geometry(self) -> "QRDPolarRequest":
        if any(depth < 0 for depth in self.well_depths_m):
            raise ValueError("well depths must be non-negative")
        if self.angles_deg is not None and any(
            not -90 <= angle <= 90 for angle in self.angles_deg
        ):
            raise ValueError("angles_deg must be in [-90, 90]")
        return self


class PolarSampleSchema(APIResponseModel):
    angle_deg: float
    normalized_pressure: float


class QRDPolarResponse(APIResponseModel):
    samples: list[PolarSampleSchema]
    frequency_hz: float
    well_width_m: float
    environment: EnvironmentResponse
    estimate_label: str


class SinglePanelTLRequest(APIModel):
    mass_per_area_kgm2: float = Field(default=50, gt=0, le=10000)
    thickness_m: float = Field(default=0.1, gt=0, le=1)
    material_type: str = Field(default="concreto", min_length=1, max_length=50)
    c_l_material: float = Field(default=0, ge=0, le=10000)
    density_kgm3: float | None = Field(default=None, gt=0, le=30000)
    young_modulus_pa: float | None = Field(default=None, gt=0, le=1e13)
    poisson_ratio: float | None = Field(default=None, gt=-1, lt=0.5)
    loss_factor: float | None = Field(default=None, gt=0, le=1)

    @model_validator(mode="after")
    def validate_material_overrides(self) -> "SinglePanelTLRequest":
        structural = (self.density_kgm3, self.young_modulus_pa, self.poisson_ratio)
        if any(value is not None for value in structural) and not all(
            value is not None for value in structural
        ):
            raise ValueError(
                "density_kgm3, young_modulus_pa, and poisson_ratio must be supplied together"
            )
        return self


class DoublePanelTLRequest(APIModel):
    m1_kgm2: float = Field(default=50, gt=0, le=10000)
    m2_kgm2: float = Field(default=50, gt=0, le=10000)
    gap_m: float = Field(default=0.05, gt=0, le=2)
    stud_connection: bool = True
    cavity_absorption: float = Field(default=0.0, ge=0, le=1)
    bridge_penalty_db: float | None = Field(default=None, ge=0, le=100)


_LEGACY_NOISE_BANDS = frozenset(ROOM_BANDS)
_NC_BANDS = frozenset(_band_key(value) for value in NC_FREQS)
_NR_BANDS = frozenset(_band_key(value) for value in NR_FREQS)
_RATING_BANDS = frozenset(_band_key(value) for value in THIRD_OCTAVE_BANDS_HZ)


class NCEvaluationRequest(APIModel):
    spl: dict[str, float] = Field(min_length=6, max_length=len(NC_FREQS))

    @field_validator("spl")
    @classmethod
    def validate_spl(cls, value: dict[str, float]) -> dict[str, float]:
        return _normalize_curve(value, (_LEGACY_NOISE_BANDS, _NC_BANDS), "NC SPL")


class NREvaluationRequest(APIModel):
    spl: dict[str, float] = Field(min_length=6, max_length=len(NR_FREQS))

    @field_validator("spl")
    @classmethod
    def validate_spl(cls, value: dict[str, float]) -> dict[str, float]:
        return _normalize_curve(value, (_LEGACY_NOISE_BANDS, _NR_BANDS), "NR SPL")


class IsolationRatingsRequest(APIModel):
    tl: dict[str, float] = Field(
        min_length=len(_RATING_BANDS), max_length=len(_RATING_BANDS)
    )

    @field_validator("tl")
    @classmethod
    def validate_tl(cls, value: dict[str, float]) -> dict[str, float]:
        return _normalize_curve(value, (_RATING_BANDS,), "third-octave TL")


class STCRatingSchema(APIResponseModel):
    stc: int
    shift: int
    contour_shift_db: int
    deficiencies: float
    total_deficiency_db: float
    max_deficiency_db: float
    deficiency_by_band_db: dict[str, float]
    contour_db: dict[str, int]
    tl_used_db: dict[str, float]
    governing_bands_hz: list[str]
    input_complete: bool
    is_estimate: bool
    input_basis: str
    method: str
    not_certification: bool
    reference: str


class RwRatingSchema(APIResponseModel):
    rw: int
    shift: int
    contour_shift_db: int
    c: int
    ctr: int
    rw_c: int
    rw_ctr: int
    spectrum_adapted_level_c_db: float
    spectrum_adapted_level_ctr_db: float
    deficiencies: float
    total_deficiency_db: float
    max_deficiency_db: float
    deficiency_by_band_db: dict[str, float]
    contour_db: dict[str, int]
    tl_used_db: dict[str, float]
    governing_bands_hz: list[str]
    input_complete: bool
    is_estimate: bool
    input_basis: str
    method: str
    not_certification: bool
    reference: str


class IsolationRatingsResponse(APIResponseModel):
    stc: STCRatingSchema
    rw: RwRatingSchema


class SinglePanelResponse(APIResponseModel):
    tl: dict[str, float]
    third_octave_tl: dict[str, float]
    fc_hz: float
    mass_per_area_kgm2: float
    thickness_m: float
    stc: int
    rw: int
    c: int
    ctr: int
    stc_details: STCRatingSchema
    rw_details: RwRatingSchema
    mass_law_asymptote_db: dict[str, float]
    coincidence_correction_db: dict[str, float]
    coincidence_depth_db: float
    material_type: str
    material_properties: dict[str, float]
    surface_mass_from_density_kgm2: float
    assumptions: list[str]
    is_estimate: bool
    reference: str


class DoublePanelResponse(APIResponseModel):
    tl: dict[str, float]
    third_octave_tl: dict[str, float]
    f0_hz: float
    m1_kgm2: float
    m2_kgm2: float
    gap_m: float
    stud_connection: bool
    stc: int
    rw: int
    c: int
    ctr: int
    stc_details: STCRatingSchema
    rw_details: RwRatingSchema
    combined_mass_asymptote_db: dict[str, float]
    independent_leaves_asymptote_db: dict[str, float]
    resonance_penalty_db: dict[str, float]
    cavity_absorption_gain_db: dict[str, float]
    bridge_penalty_db: float
    regime_by_band: dict[str, str]
    assumptions: list[str]
    is_estimate: bool
    reference: str


class NoiseRatingResponse(APIResponseModel):
    classification: str
    margin_by_band_db: dict[str, float]
    governing_bands_hz: list[str]
    above_tabulated_range: bool
    below_lowest_tabulated_curve: bool
    input_complete: bool
    is_estimate: bool
    input_basis: str
    method: str
    not_certification: bool
    reference: str
    nc: int | None = None
    nc_by_band: dict[str, int | None] | None = None
    nr: int | None = None
    nr_by_band: dict[str, int | None] | None = None


class IsolationTargetsResponse(RootModel[dict[str, dict[str, str | int]]]):
    pass


class TargetComparisonRequest(APIModel):
    uso: str = Field(min_length=1, max_length=100)
    nc: float | None = None
    nr: float | None = None
    stc: float | None = None
    rw: float | None = None

    @model_validator(mode="after")
    def require_metric(self) -> "TargetComparisonRequest":
        if all(value is None for value in (self.nc, self.nr, self.stc, self.rw)):
            raise ValueError("at least one of nc, nr, stc, or rw is required")
        return self


class TargetMetricComparisonSchema(APIResponseModel):
    value: float
    target_max: float | None = None
    target_min: float | None = None
    margin_db: float
    meets_target: bool


class TargetComparisonResponse(APIResponseModel):
    uso: str
    label: str
    comparisons: dict[str, TargetMetricComparisonSchema]
    meets_all_targets: bool
    basis: str
    not_certification: bool


class DuctAttenuationRequest(APIModel):
    width_m: float = Field(gt=0, le=100)
    height_m: float = Field(gt=0, le=100)
    length_m: float = Field(gt=0, le=1000)
    absorption_coefficients: UnitInterval | dict[str, UnitInterval]
    lined_perimeter_fraction: float = Field(default=1.0, ge=0, le=1)
    frequencies_hz: list[float] | None = Field(default=None, min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_frequency_coefficients(self) -> "DuctAttenuationRequest":
        if self.frequencies_hz is not None:
            if any(value <= 0 for value in self.frequencies_hz):
                raise ValueError("frequencies_hz must be positive")
            if len(set(self.frequencies_hz)) != len(self.frequencies_hz):
                raise ValueError("frequencies_hz must not contain duplicates")
        if isinstance(self.absorption_coefficients, dict):
            expected_values = self.frequencies_hz or [float(value) for value in ROOM_BANDS]
            expected = frozenset(_band_key(value) for value in expected_values)
            self.absorption_coefficients = _normalize_curve(
                self.absorption_coefficients, (expected,), "duct absorption"
            )
        return self


class DuctAttenuationResponse(APIResponseModel):
    insertion_loss_db: dict[str, float]
    attenuation_db_per_m: dict[str, float]
    absorption_coefficients: dict[str, float]
    cross_section_area_m2: float
    lined_perimeter_m: float
    perimeter_area_ratio_m_inv: float
    method: str
    assumptions: list[str]
    is_estimate: bool
    not_certification: bool
    reference: str


class FlankingRequest(APIModel):
    direct_tl_db: float | dict[str, float]
    flanking_paths_tl_db: list[float | dict[str, float]] = Field(
        min_length=1, max_length=32
    )

    @model_validator(mode="after")
    def validate_path_shapes(self) -> "FlankingRequest":
        direct_is_curve = isinstance(self.direct_tl_db, dict)
        if any(isinstance(path, dict) != direct_is_curve for path in self.flanking_paths_tl_db):
            raise ValueError("direct and flanking paths must all be scalars or all be curves")
        if direct_is_curve:
            direct = self.direct_tl_db
            assert isinstance(direct, dict)
            if not direct or len(direct) > 64:
                raise ValueError("direct TL curve must contain between 1 and 64 bands")
            expected = frozenset(direct)
            for path in self.flanking_paths_tl_db:
                assert isinstance(path, dict)
                if frozenset(path) != expected:
                    raise ValueError("all flanking curves must have identical bands")
        return self


class FlankingResponse(APIResponseModel):
    apparent_tl_db: float | dict[str, float]
    path_count: int
    method: str
    assumptions: list[str]
    is_estimate: bool
    not_iso_12354_prediction: bool
    reference: str


class ESSRequest(APIModel):
    f1_hz: float = Field(default=20, ge=1, le=20_000)
    f2_hz: float = Field(default=20_000, ge=2, le=48_000)
    duration_s: float = Field(default=5, ge=0.01, le=30)
    sample_rate: int = Field(default=44_100, ge=8_000, le=96_000)
    amplitude: float = Field(default=0.9, gt=0, le=1)
    fade_in_s: float = Field(default=0.01, ge=0, le=5)
    fade_out_s: float = Field(default=0.01, ge=0, le=5)
    headroom_db: float = Field(default=0, ge=0, le=120)
    bit_depth: Literal[16, 24, 32] = 16
    encoding: Literal["pcm", "float32"] = "pcm"

    @model_validator(mode="after")
    def validate_sweep(self) -> "ESSRequest":
        if self.f1_hz >= self.f2_hz:
            raise ValueError("f1_hz must be less than f2_hz")
        if self.f2_hz >= self.sample_rate / 2:
            raise ValueError("f2_hz must be strictly below Nyquist")
        if round(self.duration_s * self.sample_rate) > 2_000_000:
            raise ValueError("ESS exceeds the API sample bound")
        if self.fade_in_s + self.fade_out_s > self.duration_s:
            raise ValueError("fade durations must fit inside duration_s")
        return self


class ESSResponse(APIResponseModel):
    signal: list[float]
    sample_rate: int
    duration_s: float
    f1_hz: float
    f2_hz: float
    total_samples: int
    preview_truncated: bool


class ESSDeconvRequest(APIModel):
    response: list[float] = Field(min_length=1, max_length=MAX_SIGNAL_SAMPLES)
    ess: list[float] = Field(min_length=2, max_length=MAX_SIGNAL_SAMPLES)
    sample_rate: int = Field(default=44_100, ge=8_000, le=96_000)
    f1_hz: float | None = Field(default=None, gt=0)
    f2_hz: float | None = Field(default=None, gt=0)
    align: bool = True
    regularization: float = Field(default=1e-10, gt=0, lt=1)

    @model_validator(mode="after")
    def validate_deconvolution(self) -> "ESSDeconvRequest":
        if (self.f1_hz is None) != (self.f2_hz is None):
            raise ValueError("f1_hz and f2_hz must be supplied together")
        if self.f1_hz is not None and self.f2_hz is not None:
            if self.f1_hz >= self.f2_hz:
                raise ValueError("f1_hz must be less than f2_hz")
            if self.f2_hz >= self.sample_rate / 2:
                raise ValueError("f2_hz must be strictly below Nyquist")
        fft_size = 1 << (len(self.response) + len(self.ess) - 2).bit_length()
        if fft_size > 524_288:
            raise ValueError("deconvolution exceeds the bounded FFT size")
        return self


class DeconvolutionResponse(APIResponseModel):
    impulse_response: list[float]
    sample_rate: int
    aligned: bool
    total_samples: int


class SignalRequest(APIModel):
    signal: list[float] = Field(min_length=1, max_length=MAX_SIGNAL_SAMPLES)
    sample_rate: int = Field(default=44_100, ge=8_000, le=96_000)


class FractionalOctaveFilterRequest(SignalRequest):
    center_hz: float = Field(gt=0)
    fraction: Literal[1, 3] = 1

    @model_validator(mode="after")
    def validate_filter_band(self) -> "FractionalOctaveFilterRequest":
        upper = self.center_hz * 2.0 ** (1.0 / (2.0 * self.fraction))
        if upper >= self.sample_rate / 2:
            raise ValueError("fractional-octave upper edge must be below Nyquist")
        return self


class FractionalOctaveFilterResponse(APIResponseModel):
    signal: list[float]
    sample_rate: int
    center_hz: float
    fraction: int
    band_edges_hz: tuple[float, float]


class IRAnalysisRequest(APIModel):
    ir: list[float] = Field(min_length=1, max_length=MAX_SIGNAL_SAMPLES)
    sample_rate: int = Field(default=44_100, ge=8_000, le=96_000)
    direct_delay_ms: float = Field(default=0, ge=0)
    metric_context: Literal["predicted_model", "measured"] = "measured"


class IRAnalysisResponse(APIResponseModel):
    sample_rate: int
    total_samples: int
    parameters: ISO3382ParametersSchema | MeasurementErrorSchema


class WaterfallRequest(APIModel):
    ir: list[float] = Field(min_length=1, max_length=MAX_SIGNAL_SAMPLES)
    sample_rate: int = Field(default=44_100, ge=8_000, le=96_000)
    duration_s: float = Field(default=1.0, ge=0.01, le=5)
    fraction: Literal[1, 3] = 1
    centers_hz: list[float] | None = Field(default=None, min_length=1, max_length=32)
    time_step_s: float = Field(default=0.01, gt=0, le=1)
    floor_db: float = Field(default=-120, ge=-300, lt=0)

    @model_validator(mode="after")
    def validate_waterfall(self) -> "WaterfallRequest":
        if round(self.sample_rate * self.duration_s) > MAX_SIGNAL_SAMPLES:
            raise ValueError("waterfall duration exceeds the API sample bound")
        centers = self.centers_hz or [float(value) for value in ROOM_BANDS]
        if len(set(centers)) != len(centers) or any(value <= 0 for value in centers):
            raise ValueError("centers_hz must contain unique positive frequencies")
        if any(
            value * 2.0 ** (1.0 / (2.0 * self.fraction)) >= self.sample_rate / 2
            for value in centers
        ):
            raise ValueError("all waterfall band edges must be below Nyquist")
        return self


class WaterfallResponse(APIResponseModel):
    time_ms: list[float]
    bands: dict[str, list[float]]
    band_edges_hz: dict[str, tuple[float, float]]
    sample_rate: int
    duration_s: float
    fraction: int
    floor_db: float
    representation: str


class SpectrogramRequest(APIModel):
    signal: list[float] = Field(min_length=1, max_length=MAX_SPECTROGRAM_SAMPLES)
    sample_rate: int = Field(default=44_100, ge=8_000, le=96_000)
    window_size: int = Field(default=1024, ge=2, le=16384)
    hop_size: int | None = Field(default=None, ge=1, le=16384)
    floor_db: float = Field(default=-120, ge=-300, lt=0)
    max_frames: int = Field(default=1024, ge=1, le=4096)

    @model_validator(mode="after")
    def validate_spectrogram_size(self) -> "SpectrogramRequest":
        hop = self.hop_size or self.window_size // 2
        frames = max(1, 1 + max(0, len(self.signal) - self.window_size) // hop)
        fft_size = 1 << (self.window_size - 1).bit_length()
        if frames > self.max_frames:
            raise ValueError("spectrogram frame count exceeds max_frames")
        if frames * (fft_size // 2 + 1) > 2_000_000:
            raise ValueError("spectrogram output exceeds the API matrix bound")
        return self


class SpectrogramResponse(APIResponseModel):
    times_s: list[float]
    frequencies_hz: list[float]
    magnitude: list[list[float]]
    magnitude_db: list[list[float]]
    sample_rate: int
    window_size: int
    fft_size: int
    hop_size: int
    window: str
    floor_db: float


class ModalQRequest(SignalRequest):
    target_frequency_hz: float | None = Field(default=None, gt=0)
    cycles_per_window: float = Field(default=4, ge=2, le=100)
    dynamic_range_db: float = Field(default=30, ge=10, le=80)

    @model_validator(mode="after")
    def validate_target_frequency(self) -> "ModalQRequest":
        if (
            self.target_frequency_hz is not None
            and self.target_frequency_hz >= self.sample_rate / 2
        ):
            raise ValueError("target_frequency_hz must be strictly below Nyquist")
        return self


class ModalQResponse(APIResponseModel):
    Q: float
    q: float
    frequency_hz: float
    decay_slope_nepers_per_s: float
    intercept_log_amplitude: float
    r2: float
    fit_points: int
    dynamic_range_db: float
    method: str


class CalibrateRequest(RoomRequest):
    measured_rt60: dict[str, PositiveFinite] = Field(
        min_length=1, max_length=len(ROOM_BANDS)
    )
    iterations: int = Field(default=30, ge=1, le=200)

    @field_validator("measured_rt60")
    @classmethod
    def validate_measured_bands(cls, value: dict[str, float]) -> dict[str, float]:
        unknown = sorted(set(value) - ROOM_BAND_SET)
        if unknown:
            raise ValueError(f"unknown measured octave bands: {', '.join(unknown)}")
        return value


class CalibrationDiagnosticSchema(APIResponseModel):
    converged: bool
    reason: str | None
    iterations: int
    objective_history: list[float]
    absolute_error_history_s: list[float]
    initial_predicted_rt60_s: float
    predicted_rt60_s: float
    measured_rt60_s: float
    target_absorption_m2_sabins: float
    common_alpha_offset: float
    alpha_bounds: tuple[float, float]
    grouping: str
    identifiable_parameters: int
    surface_coefficients_reported: int


class CalibrateResponse(APIResponseModel):
    calibrated_alphas: dict[str, dict[str, float]]
    diagnostics: dict[str, CalibrationDiagnosticSchema]
    measured_rt60: dict[str, float]


class WavAnalysisResponse(APIResponseModel):
    filename: str | None
    sample_rate: int
    num_channels: int
    num_frames: int
    bits_per_sample: int
    audio_format: str
    selected_channel: int | Literal["mix"]
    samples_preview: list[float]
    preview_truncated: bool
    parameters: ISO3382ParametersSchema | MeasurementErrorSchema | None = None


class FiniteImpedanceRequest(APIModel):
    L_m: float = Field(default=5, gt=0, le=50)
    W_m: float = Field(default=4, gt=0, le=50)
    H_m: float = Field(default=3, gt=0, le=50)
    Z_wall: float = Field(default=10000, gt=0, le=1e12)
    Z_wall_imag: float = Field(default=0, ge=-1e12, le=1e12)
    max_order: int = Field(default=3, ge=1, le=5)
    density_kgm3: float = Field(default=1.2, gt=0, le=100)
    environment: EnvironmentRequest = Field(default_factory=EnvironmentRequest)


class FiniteAxialModeSchema(APIResponseModel):
    n: int
    frequency_hz: float
    frequency_imag_hz: float
    rigid_frequency_hz: float
    damping_neper_s: float
    decay_rate_neper_s: float
    rt60_estimate_s: float
    shift_hz: float
    residual: float
    converged: bool
    boundary_configuration: str


class FiniteRoomModeSchema(APIResponseModel):
    indices: tuple[int, int, int]
    frequency_hz: float
    frequency_imag_hz: float
    rigid_frequency_hz: float
    damping: float
    damping_neper_s: float
    rt60_estimate_s: float
    residual: float
    model: str


class FiniteImpedanceResponse(APIResponseModel):
    axial_modes: list[FiniteAxialModeSchema]
    room_modes: list[FiniteRoomModeSchema]
    Z_wall: float
    Z_wall_imag: float
    density_kgm3: float
    environment: EnvironmentResponse
    research_status: str


class ExclusionRegion(APIModel):
    x0: float
    y0: float
    x1: float
    y1: float


class FEM2DRequest(APIModel):
    width: float = Field(default=5, gt=0, le=50)
    height: float = Field(default=4, gt=0, le=50)
    grid_nx: int = Field(default=20, ge=5, le=80)
    grid_ny: int = Field(default=20, ge=5, le=80)
    num_modes: int = Field(default=5, ge=1, le=20)
    exclude_regions: list[ExclusionRegion] = Field(default_factory=list, max_length=16)
    exclude_region: str = Field(
        default="",
        max_length=200,
        description="Deprecated single x0,y0,x1,y1 exclusion; use exclude_regions.",
    )
    boundary_impedance_real: float | None = Field(default=None, gt=0, le=1e12)
    boundary_impedance_imag: float = Field(default=0, ge=-1e12, le=1e12)
    density_kgm3: float = Field(default=1.2, gt=0, le=100)
    environment: EnvironmentRequest = Field(default_factory=EnvironmentRequest)

    @model_validator(mode="after")
    def validate_exclusions(self) -> "FEM2DRequest":
        if self.exclude_region:
            if self.exclude_regions:
                raise ValueError("use exclude_region or exclude_regions, not both")
            parts = self.exclude_region.split(",")
            if len(parts) != 4:
                raise ValueError("exclude_region must be x0,y0,x1,y1")
            try:
                coordinates = [float(part.strip()) for part in parts]
            except ValueError as exc:
                raise ValueError("exclude_region coordinates must be finite numbers") from exc
            if not all(math.isfinite(value) for value in coordinates):
                raise ValueError("exclude_region coordinates must be finite numbers")
            self.exclude_regions = [ExclusionRegion(
                x0=coordinates[0], y0=coordinates[1], x1=coordinates[2], y1=coordinates[3]
            )]
        for region in self.exclude_regions:
            if not (0 <= region.x0 < region.x1 <= self.width):
                raise ValueError("FEM exclusion x bounds must satisfy 0 <= x0 < x1 <= width")
            if not (0 <= region.y0 < region.y1 <= self.height):
                raise ValueError("FEM exclusion y bounds must satisfy 0 <= y0 < y1 <= height")
            if (
                region.x0 == 0
                and region.y0 == 0
                and region.x1 == self.width
                and region.y1 == self.height
            ):
                raise ValueError("FEM exclusion must not remove the entire domain")
        return self


class FEMModeSchema(APIResponseModel):
    mode: int
    frequency_hz: float
    frequency_imag_hz: float
    decay_rate_neper_s: float
    rt60_estimate_s: float
    eigenvalue_per_m2: float
    residual: float
    shape_2d: list[list[float]]
    grid_x: list[float]
    grid_y: list[float]
    mesh_nodes: int
    mesh_triangles: int
    method: str
    research_status: str


class FEM2DResponse(APIResponseModel):
    modes: list[FEMModeSchema]
    width: float
    height: float
    boundary_condition: str
    environment: EnvironmentResponse


class PolygonFEMRequest(APIModel):
    vertices: list[Point2D] = Field(min_length=3, max_length=64)
    target_edge_length_m: float = Field(gt=0.02, le=10)
    num_modes: int = Field(default=5, ge=1, le=20)
    boundary_impedance_real: float | None = Field(default=None, gt=0, le=1e12)
    boundary_impedance_imag: float = Field(default=0, ge=-1e12, le=1e12)
    density_kgm3: float = Field(default=1.2, gt=0, le=100)
    room_height_m: float | None = Field(default=None, gt=0, le=1000)
    max_vertical_order: int = Field(default=0, ge=0, le=20)
    environment: EnvironmentRequest = Field(default_factory=EnvironmentRequest)

    @model_validator(mode="after")
    def validate_polygon_bound(self) -> "PolygonFEMRequest":
        if self.vertices[0] == self.vertices[-1]:
            self.vertices = self.vertices[:-1]
        if len(self.vertices) < 3 or len(set(self.vertices)) < 3:
            raise ValueError("polygon requires at least three distinct vertices")
        if any(left == right for left, right in zip(self.vertices, self.vertices[1:] + self.vertices[:1])):
            raise ValueError("polygon must not contain zero-length edges")
        xs = [point[0] for point in self.vertices]
        ys = [point[1] for point in self.vertices]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        if span_x <= 0 or span_y <= 0:
            raise ValueError("polygon must span both coordinate axes")
        estimated_grid = (
            (math.ceil(span_x / self.target_edge_length_m) + 1)
            * (math.ceil(span_y / self.target_edge_length_m) + 1)
        )
        if estimated_grid > 20_000:
            raise ValueError("polygon mesh request exceeds the node bound")
        if self.max_vertical_order and self.room_height_m is None:
            raise ValueError("room_height_m is required when max_vertical_order is non-zero")
        return self


class PolygonFEMModeSchema(APIResponseModel):
    mode: int
    frequency_hz: float
    frequency_imag_hz: float
    decay_rate_neper_s: float
    rt60_estimate_s: float
    eigenvalue_real_per_m2: float
    eigenvalue_imag_per_m2: float
    residual: float
    shape_real: list[float]
    shape_imag: list[float]


class CoupledModeSchema(APIResponseModel):
    horizontal_mode_index: int
    vertical_order: int
    frequency_hz: float
    frequency_imag_hz: float
    decay_rate_neper_s: float
    rt60_estimate_s: float


class PolygonFEMResponse(APIResponseModel):
    nodes: list[Point2D]
    elements: list[tuple[int, int, int]]
    boundary_markers: list[int]
    nominal_spacing_m: float
    modes: list[PolygonFEMModeSchema]
    coupled_modes: list[CoupledModeSchema]
    method: str
    boundary_condition: str
    environment: EnvironmentResponse
    research_status: str


class RayTraceRequest(SourceReceiverRoomRequest):
    num_rays: int = Field(default=300, ge=50, le=5000)
    max_reflections: int = Field(default=30, ge=0, le=100)
    max_time_s: float = Field(default=1.0, gt=0, le=5)
    listener_radius_m: float = Field(default=0.15, gt=0, le=5)
    scattering: float = Field(default=0, ge=0, le=1)
    seed: int = Field(default=0, ge=0, le=4_294_967_295)
    bands_hz: list[float] = Field(
        default_factory=lambda: [float(value) for value in ROOM_BANDS],
        min_length=1,
        max_length=32,
    )

    @model_validator(mode="after")
    def validate_ray_bands(self) -> "RayTraceRequest":
        if any(value <= 0 for value in self.bands_hz):
            raise ValueError("bands_hz must be positive")
        if any(left >= right for left, right in zip(self.bands_hz, self.bands_hz[1:])):
            raise ValueError("bands_hz must be strictly increasing")
        if self.num_rays * max(1, self.max_reflections) > 250_000:
            raise ValueError("ray/reflection combination exceeds the compute bound")
        return self


class SurfaceStatisticsSchema(APIResponseModel):
    hit_count: int
    diffuse_events: int
    incident_energy_by_band: list[float]
    absorbed_energy_by_band: list[float]


class RayTraceResponse(APIResponseModel):
    bands_hz: list[float]
    time_s: list[float]
    energy_by_band: dict[str, list[float]]
    energy_db_by_band: dict[str, list[float]]
    total_energy_by_band: dict[str, float]
    rt60_s_by_band: dict[str, float]
    direct_time_s: float | None
    total_ray_segments: int
    terminated_ray_count: int
    seed: int
    surface_statistics: dict[str, SurfaceStatisticsSchema]
    bvh_statistics: dict[str, int]
    research_status: str
    num_rays: int
    energy_time_s: list[float]
    energy_db: list[float]
    rt60_estimate_s: float
    method: str
    environment: EnvironmentResponse


class HybridRequest(SourceReceiverRoomRequest):
    num_rays: int = Field(default=300, ge=50, le=5000)
    max_reflections: int = Field(default=30, ge=0, le=100)
    max_ism_order: int = Field(default=6, ge=0, le=15)
    seed: int = Field(default=0, ge=0, le=4_294_967_295)
    crossover_octaves: float = Field(default=1.0, gt=0, le=4)

    @model_validator(mode="after")
    def validate_hybrid_bound(self) -> "HybridRequest":
        if self.num_rays * max(1, self.max_reflections) > 250_000:
            raise ValueError("hybrid ray/reflection combination exceeds the compute bound")
        return self


class HybridFrequencyBranchSchema(APIResponseModel):
    method: str
    quantity: str
    values: list[float]


class HybridFrequencyResponseSchema(APIResponseModel):
    frequencies_hz: list[float]
    low_frequency: HybridFrequencyBranchSchema
    high_frequency: HybridFrequencyBranchSchema
    combined_values: list[float]
    low_weights: list[float]
    high_weights: list[float]
    schroeder_frequency_hz: float
    crossover_octaves: float
    research_status: str


class HybridISMSchema(APIResponseModel):
    image_sources: int
    max_order: int
    iso_3382: ISO3382ParametersSchema | MeasurementErrorSchema
    frequency_energy: dict[str, float]


class HybridRaySchema(APIResponseModel):
    num_rays: int
    energy_time_s: list[float]
    energy_db: list[float]
    rt60_estimate_s: float
    frequency_energy: dict[str, float]
    seed: int


class HybridLegacySchema(APIResponseModel):
    rt60_estimate_s: float
    rt60_note: str
    weight_ism: float
    weight_ray_tracing: float
    frequencies_hz: list[float]
    energy: list[float]


class HybridResponse(APIResponseModel):
    schroeder_frequency_hz: float
    modal_count_below_schroeder: int
    ism: HybridISMSchema
    ray_tracing: HybridRaySchema
    low_frequency: HybridFrequencyBranchSchema
    high_frequency: HybridFrequencyBranchSchema
    frequency_response: HybridFrequencyResponseSchema
    hybrid: HybridLegacySchema
    environment: EnvironmentResponse
    research_status: str


class LicenseStatusResponse(APIResponseModel):
    authenticated: Literal[True] = True
    user_id: UUID
    license_id: UUID
    api_key_id: UUID
    email: str
    tier: Literal["FREE", "PAID", "RESEARCH"]
    key_prefix: str
    entitlements: list[str]
    quotas: dict[str, int]


class JobStatusResponse(APIResponseModel):
    id: UUID
    kind: str
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    result: dict[str, object] | None
    error: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobSubmitRequest(APIModel):
    kind: str = Field(min_length=1, max_length=100)
    payload: dict[str, object] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=200)
    max_attempts: int = Field(default=3, ge=1, le=10)


class StoredAssetResponse(APIResponseModel):
    id: UUID
    filename: str
    content_type: str
    category: str
    size_bytes: int
    sha256: str
    status: Literal["PENDING", "READY", "DELETING", "FAILED"]
    created_at: datetime


class StoredAssetListResponse(APIResponseModel):
    items: list[StoredAssetResponse]
    total: int
    offset: int
    limit: int


class StorageUsageResponse(APIResponseModel):
    used_bytes: int
    limit_bytes: int
    remaining_bytes: int
    object_count: int
    usage_percent: float


class StorageMetricsResponse(APIResponseModel):
    by_status: dict[str, dict[str, int]]
    by_category: dict[str, dict[str, int]]
    backend_available: bool


class ProjectCreateRequest(APIModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)


class ProjectUpdateRequest(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    archived: bool | None = None


class ProjectResponse(APIResponseModel):
    id: UUID
    name: str
    description: str | None
    archived: bool
    created_at: datetime
    updated_at: datetime


class CalculationCreateRequest(APIModel):
    kind: str = Field(min_length=1, max_length=100)
    input_data: dict[str, object] = Field(default_factory=dict)
    result_data: dict[str, object] | None = None
    core_version: str | None = Field(default=None, max_length=50)


class CalculationResponse(APIResponseModel):
    id: UUID
    project_id: UUID
    kind: str
    input_data: dict[str, object]
    result_data: dict[str, object] | None
    core_version: str | None
    created_at: datetime

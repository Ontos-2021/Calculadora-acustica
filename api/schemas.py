from typing import Optional
from pydantic import BaseModel, Field


class SurfaceRequest(BaseModel):
    material: str = "Concreto"
    alphas: Optional[dict[str, float]] = None


class CalculateRequest(BaseModel):
    largo: float = Field(gt=0)
    ancho: float = Field(gt=0)
    alto: float = Field(gt=0)
    uso: Optional[str] = None
    superficies: list[SurfaceRequest] = Field(default=[SurfaceRequest()] * 6, min_length=6, max_length=6)


class ModeSchema(BaseModel):
    indices: list[int]
    frecuencia: float
    tipo: str
    peso_db: float
    degenerado: bool = False
    solapado: bool = False


class BonelloSchema(BaseModel):
    cumple: bool
    bandas: dict[float, int]
    violaciones: list[int]
    total_modos: int


class ProporcionSchema(BaseModel):
    proporcion_actual: tuple[float, float, float]
    mas_cercana: str
    proporcion_cercana: tuple[float, float, float]
    error: float
    todas: list[tuple[str, float, float]]


class ObjetivoSchema(BaseModel):
    label: str
    valores: dict[str, float]
    diferencias: Optional[dict[str, float]] = None


class CalculateResponse(BaseModel):
    modos: list[ModeSchema]
    frecuencias: list[float]
    cantidad_modos: int
    distribucion: dict[str, int]
    rt60_bandas: dict[str, dict[str, float]]
    rt60_promedio: float
    f_schroeder: float
    delta_f: float
    bonello: BonelloSchema
    proporciones: ProporcionSchema
    degeneracion_dimensiones: list[str]
    objetivo: Optional[ObjetivoSchema] = None


class PressureMapRequest(BaseModel):
    largo: float = Field(gt=0)
    ancho: float = Field(gt=0)
    alto: float = Field(gt=0)
    superficies: list[SurfaceRequest] = Field(default=[SurfaceRequest()] * 6, min_length=6, max_length=6)
    ear_height: float = Field(default=1.2, gt=0, le=10)
    max_freq: float = Field(default=300.0, gt=0, le=1000)
    grid_size: int = Field(default=100, ge=10, le=200)
    mode_indices: Optional[list[int]] = None


class PressureMapResponse(BaseModel):
    grid_x: list[float]
    grid_y: list[float]
    pressure: list[list[float]]
    max_freq: float
    ear_height: float
    num_modos: int
    optimal_listening: dict


class IRRequest(BaseModel):
    largo: float = Field(gt=0)
    ancho: float = Field(gt=0)
    alto: float = Field(gt=0)
    superficies: list[SurfaceRequest] = Field(default=[SurfaceRequest()] * 6, min_length=6, max_length=6)
    source: list[float] = Field(default=[1.0, 1.0, 1.5], min_length=3, max_length=3)
    receiver: list[float] = Field(default=[4.0, 3.0, 1.2], min_length=3, max_length=3)
    max_order: int = Field(default=8, ge=1, le=15)
    sample_rate: int = Field(default=44100, ge=8000, le=96000)


class IRResponse(BaseModel):
    impulse_response: list[float]
    sample_rate: int
    direct_delay_ms: float
    parameters: dict


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0"
    core_version: str = "0.1"


class MaterialResponse(BaseModel):
    nombre: str
    categoria: str
    alphas: dict[str, float]
    alpha_w: Optional[float] = None
    iso_class: str


class MaterialSearchRequest(BaseModel):
    query: str = ""
    categoria: str = ""
    min_alpha_w: float = Field(default=0.0, ge=0, le=1)
    max_alpha_w: float = Field(default=1.0, ge=0, le=1)
    iso_class: str = ""


class AirAbsorptionRequest(BaseModel):
    humidity: float = Field(default=50.0, ge=0, le=100)
    temp_celsius: float = Field(default=20.0, ge=-10, le=50)


class AirAbsorptionResponse(BaseModel):
    coeficientes: dict[str, float]
    humidity: float
    temp_celsius: float


class AudienceAbsorptionRequest(BaseModel):
    num_people: int = Field(default=0, ge=0)
    seated: bool = True
    upholstered: bool = True
    occupied: float = Field(default=0.85, ge=0, le=1)


class InverseDesignRequest(BaseModel):
    largo: float = Field(gt=0)
    ancho: float = Field(gt=0)
    alto: float = Field(gt=0)
    superficies: list[SurfaceRequest] = Field(default=[SurfaceRequest()] * 6, min_length=6, max_length=6)
    target_uso: str
    include_placement: bool = False


class MaterialSuggestion(BaseModel):
    material: str
    area_needed_m2: float
    alpha_w: Optional[float] = None
    iso_class: str
    categoria: str
    per_band: dict[str, float]


class PlacementSuggestion(BaseModel):
    surface: str
    surface_area_m2: float
    missing_absorption_m2: float
    priority_score: float
    coverage_percent: float


class InverseDesignResponse(BaseModel):
    current_absorption: dict[str, float]
    required_absorption: dict[str, float]
    missing_absorption: dict[str, float]
    material_suggestions: list[MaterialSuggestion]
    placement_suggestions: list[PlacementSuggestion] = []

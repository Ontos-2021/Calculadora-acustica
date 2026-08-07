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


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0"
    core_version: str = "0.1"

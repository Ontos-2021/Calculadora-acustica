from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field, model_validator


BANDAS_OCTAVA = ["125", "250", "500", "1000", "2000", "4000"]


class ModeType(Enum):
    AXIAL = "axial"
    TANGENTIAL = "tangencial"
    OBLIQUE = "oblicuo"


class Material(BaseModel):
    nombre: str
    alphas: dict[str, float] = Field(default_factory=dict)
    alpha_unico: Optional[float] = None

    @model_validator(mode='after')
    def validar_alphas(self):
        if self.alpha_unico is not None:
            if not (0 <= self.alpha_unico <= 1):
                raise ValueError(f"alpha_unico debe estar entre 0 y 1, got {self.alpha_unico}")
        for banda, alpha in self.alphas.items():
            if banda not in BANDAS_OCTAVA:
                raise ValueError(f"Banda desconocida: {banda}")
            if not (0 <= alpha <= 1):
                raise ValueError(f"α para banda {banda} debe estar entre 0 y 1")
        if not self.alphas and self.alpha_unico is None:
            raise ValueError("Debe proporcionar alphas por banda o alpha_unico")
        return self

    @property
    def alpha(self) -> dict[str, float]:
        if self.alpha_unico is not None:
            return {b: self.alpha_unico for b in BANDAS_OCTAVA}
        return self.alphas


class Surface(BaseModel):
    nombre: str
    area: float = Field(gt=0)
    material: Material


class Room(BaseModel):
    largo: float = Field(gt=0)
    ancho: float = Field(gt=0)
    alto: float = Field(gt=0)
    superficies: list[Surface] = Field(min_length=6, max_length=6)
    uso: Optional[str] = None

    @property
    def volumen(self) -> float:
        return self.largo * self.ancho * self.alto

    @property
    def superficie_total(self) -> float:
        return sum(s.area for s in self.superficies)


class Mode(BaseModel):
    indices: list[int]
    frecuencia: float
    tipo: ModeType
    peso_db: float
    degenerado: bool = False
    solapado: bool = False

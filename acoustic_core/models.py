from enum import Enum
import math
from typing import Optional
import warnings

from pydantic import BaseModel, Field, field_validator, model_validator

from .environment import Environment
from .spectrum import ROOM_OCTAVE_BANDS, Spectrum
from .uncertainty import Uncertainty


BANDAS_OCTAVA = [f"{center:g}" for center in ROOM_OCTAVE_BANDS.centers_hz]


class PartialAbsorptionWarning(UserWarning):
    """A partial spectrum required an explicitly reported inferred baseline."""


class ModeType(Enum):
    AXIAL = "axial"
    TANGENTIAL = "tangencial"
    OBLIQUE = "oblicuo"


class Material(BaseModel):
    nombre: str
    alphas: dict[str, float] = Field(default_factory=dict)
    alpha_unico: Optional[float] = None
    categoria: str = ""
    alpha_w: Optional[float] = None
    iso_class: str = ""
    provenance: Optional[str] = None
    uncertainty: Optional[Uncertainty] = None

    @model_validator(mode='after')
    def validar_alphas(self):
        if self.alpha_unico is not None:
            if not math.isfinite(self.alpha_unico) or not (0 <= self.alpha_unico <= 1):
                raise ValueError(f"alpha_unico debe estar entre 0 y 1, got {self.alpha_unico}")
        for banda, alpha in self.alphas.items():
            if banda not in BANDAS_OCTAVA:
                raise ValueError(f"Banda desconocida: {banda}")
            if not math.isfinite(alpha) or not (0 <= alpha <= 1):
                raise ValueError(f"α para banda {banda} debe estar entre 0 y 1")
        if not self.alphas and self.alpha_unico is None:
            raise ValueError("Debe proporcionar alphas por banda o alpha_unico")
        if self.alpha_unico is None and set(self.alphas) != set(BANDAS_OCTAVA):
            faltantes = [banda for banda in BANDAS_OCTAVA if banda not in self.alphas]
            self.alpha_unico = sum(self.alphas.values()) / len(self.alphas)
            warnings.warn(
                "Partial absorption spectrum: alpha_unico was inferred as the "
                f"mean of supplied bands ({self.alpha_unico:.6g}) and used for "
                f"missing bands: {', '.join(faltantes)}.",
                PartialAbsorptionWarning,
                stacklevel=2,
            )
        if self.provenance is not None:
            self.provenance = self.provenance.strip()
            if not self.provenance:
                raise ValueError("provenance no puede estar vacio")
        if self.alpha_w is not None:
            if not math.isfinite(self.alpha_w) or not 0.0 <= self.alpha_w <= 1.0:
                raise ValueError("alpha_w debe estar entre 0 y 1")
        return self

    @property
    def alpha(self) -> dict[str, float]:
        if self.alpha_unico is None:
            return {banda: self.alphas[banda] for banda in BANDAS_OCTAVA}
        resultado = {banda: self.alpha_unico for banda in BANDAS_OCTAVA}
        resultado.update(self.alphas)
        return resultado

    def alpha_at(self, banda: str) -> float:
        if banda not in BANDAS_OCTAVA:
            raise ValueError(f"Banda desconocida: {banda}")
        return self.alpha[banda]

    @property
    def alpha_spectrum(self) -> Spectrum:
        alpha = self.alpha
        return Spectrum(
            bands=ROOM_OCTAVE_BANDS,
            values=tuple(alpha[banda] for banda in BANDAS_OCTAVA),
            unit="1",
            name=f"Absorption coefficient - {self.nombre}",
            provenance=self.provenance,
        )


class Surface(BaseModel):
    nombre: str
    area: float = Field(gt=0)
    material: Material

    @field_validator("area")
    @classmethod
    def validar_area_finita(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("area debe ser finita")
        return value


class Room(BaseModel):
    largo: float = Field(gt=0)
    ancho: float = Field(gt=0)
    alto: float = Field(gt=0)
    superficies: list[Surface] = Field(min_length=6, max_length=6)
    uso: Optional[str] = None
    environment: Environment = Field(default_factory=Environment)
    provenance: Optional[str] = None
    uncertainty: Optional[Uncertainty] = None

    @field_validator("largo", "ancho", "alto")
    @classmethod
    def validar_dimension_finita(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("las dimensiones deben ser finitas")
        return value

    @field_validator("provenance")
    @classmethod
    def validar_provenance(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("provenance no puede estar vacio")
        return value

    @model_validator(mode="after")
    def validar_agregados_geometricos(self):
        if not math.isfinite(self.largo * self.ancho * self.alto):
            raise ValueError("el volumen de la sala debe ser finito")
        if not math.isfinite(sum(surface.area for surface in self.superficies)):
            raise ValueError("la superficie total debe ser finita")
        return self

    @property
    def volumen(self) -> float:
        return self.largo * self.ancho * self.alto

    @property
    def superficie_total(self) -> float:
        return sum(s.area for s in self.superficies)

    @property
    def sound_speed(self) -> float:
        return self.environment.sound_speed_m_s


class Mode(BaseModel):
    indices: list[int]
    frecuencia: float
    tipo: ModeType
    peso_db: float
    degenerado: bool = False
    solapado: bool = False
    multiplicity: int = Field(default=1, ge=1)
    degeneracy_cluster: Optional[int] = Field(default=None, ge=0)
    overlap_multiplicity: int = Field(default=1, ge=1)
    overlap_cluster: Optional[int] = Field(default=None, ge=0)

    @field_validator("indices", mode="before")
    @classmethod
    def validar_indices_originales(cls, value):
        if not isinstance(value, (list, tuple)):
            raise TypeError("indices debe ser una lista o tupla")
        if any(isinstance(index, bool) for index in value):
            raise ValueError("los indices modales no aceptan booleanos")
        return value

    @model_validator(mode="after")
    def validar_modo(self):
        if len(self.indices) != 3:
            raise ValueError("indices debe contener exactamente tres ordenes modales")
        if any(isinstance(index, bool) or index < 0 for index in self.indices):
            raise ValueError("los indices modales deben ser enteros no negativos")
        if self.indices == [0, 0, 0]:
            raise ValueError("el modo (0, 0, 0) no existe")
        if not math.isfinite(self.frecuencia) or self.frecuencia <= 0.0:
            raise ValueError("frecuencia debe ser finita y positiva")
        if not math.isfinite(self.peso_db):
            raise ValueError("peso_db debe ser finito")
        if not -3000.0 <= self.peso_db <= 0.0:
            raise ValueError("peso_db debe estar entre -3000 y 0 dB relativos")
        return self

    @property
    def frequency_hz(self) -> float:
        return self.frecuencia

    @property
    def energy_weight(self) -> float:
        return 10.0 ** (self.peso_db / 10.0)

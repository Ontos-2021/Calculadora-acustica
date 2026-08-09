"""Frequency-dependent reverberation calculations for rectangular rooms."""

from __future__ import annotations

from dataclasses import dataclass
import math
import warnings

from .environment import Environment
from .models import BANDAS_OCTAVA, Room


SABINE_CONSTANT_S_M = 0.161
# Legacy aggregate functions promise floats.  This finite, documented value is
# used only where the physical result is unbounded; structured results use None.
RT60_UNBOUNDED_SENTINEL = 1_000_000.0


class SabineApplicabilityWarning(UserWarning):
    """Raised when mean absorption is outside Sabine's usual range."""


@dataclass(frozen=True, slots=True)
class RT60Estimate:
    method: str
    band: str
    value_seconds: float | None
    mean_absorption: float
    warnings: tuple[str, ...] = ()

    @property
    def is_bounded(self) -> bool:
        return self.value_seconds is not None


@dataclass(frozen=True, slots=True)
class ReverberationResult:
    """Finite-or-optional RT60 estimates with diagnostics."""

    estimates: tuple[RT60Estimate, ...]

    def get(self, band: str, method: str) -> RT60Estimate:
        for estimate in self.estimates:
            if estimate.band == band and estimate.method == method:
                return estimate
        raise KeyError(f"No {method} estimate for {band} Hz")

    @property
    def warnings(self) -> tuple[str, ...]:
        unique: list[str] = []
        for estimate in self.estimates:
            for message in estimate.warnings:
                if message not in unique:
                    unique.append(message)
        return tuple(unique)

    def as_legacy_dict(
        self,
        unbounded_sentinel: float = RT60_UNBOUNDED_SENTINEL,
    ) -> dict[str, dict[str, float]]:
        if not math.isfinite(unbounded_sentinel) or unbounded_sentinel <= 0.0:
            raise ValueError("unbounded_sentinel must be finite and positive")
        result = {band: {} for band in BANDAS_OCTAVA}
        for estimate in self.estimates:
            value = estimate.value_seconds
            result[estimate.band][estimate.method] = (
                value if value is not None else unbounded_sentinel
            )
        return result


def _validate_band(banda: str) -> None:
    if banda not in BANDAS_OCTAVA:
        raise ValueError(f"Banda desconocida: {banda}")


def _absorcion_total(room: Room, banda: str) -> float:
    _validate_band(banda)
    return sum(surface.area * surface.material.alpha_at(banda) for surface in room.superficies)


def _a_promedio(room: Room, banda: str) -> float:
    return _absorcion_total(room, banda) / room.superficie_total


def _resolve_air_attenuation(
    room: Room,
    banda: str,
    *,
    environment: Environment | None,
    include_air_attenuation: bool,
    air_attenuation_m_inv: float | None,
) -> float:
    if air_attenuation_m_inv is not None:
        coefficient = float(air_attenuation_m_inv)
        if not math.isfinite(coefficient) or coefficient < 0.0:
            raise ValueError("air_attenuation_m_inv must be finite and non-negative")
        return coefficient
    if not include_air_attenuation:
        return 0.0
    return (environment or room.environment).air_attenuation_m_inv(float(banda))


def _apply_air_attenuation(surface_rt: float, room: Room, coefficient: float) -> float:
    if coefficient <= 0.0:
        return surface_rt
    air_absorption_area = 4.0 * coefficient * room.volumen
    if surface_rt == 0.0:
        return 0.0
    if math.isinf(surface_rt):
        return SABINE_CONSTANT_S_M * room.volumen / air_absorption_area
    equivalent_surface_absorption = SABINE_CONSTANT_S_M * room.volumen / surface_rt
    return (
        SABINE_CONSTANT_S_M
        * room.volumen
        / (equivalent_surface_absorption + air_absorption_area)
    )


def _sabine_warning(room: Room, banda: str) -> str | None:
    mean_absorption = _a_promedio(room, banda)
    if mean_absorption > 0.2:
        return (
            f"Sabine at {banda} Hz is outside its usual applicability range: "
            f"mean absorption={mean_absorption:.6g} > 0.2; prefer Eyring."
        )
    return None


def rt60_sabine(
    room: Room,
    banda: str,
    *,
    environment: Environment | None = None,
    include_air_attenuation: bool = False,
    air_attenuation_m_inv: float | None = None,
    warn: bool = True,
) -> float:
    absorption = _absorcion_total(room, banda)
    message = _sabine_warning(room, banda)
    if message is not None and warn:
        warnings.warn(message, SabineApplicabilityWarning, stacklevel=2)
    surface_rt = math.inf if absorption <= 0.0 else SABINE_CONSTANT_S_M * room.volumen / absorption
    coefficient = _resolve_air_attenuation(
        room,
        banda,
        environment=environment,
        include_air_attenuation=include_air_attenuation,
        air_attenuation_m_inv=air_attenuation_m_inv,
    )
    return _apply_air_attenuation(surface_rt, room, coefficient)


def rt60_eyring(
    room: Room,
    banda: str,
    *,
    environment: Environment | None = None,
    include_air_attenuation: bool = False,
    air_attenuation_m_inv: float | None = None,
) -> float:
    mean_absorption = _a_promedio(room, banda)
    if mean_absorption >= 1.0:
        surface_rt = 0.0
    elif mean_absorption <= 0.0:
        surface_rt = math.inf
    else:
        surface_rt = (
            SABINE_CONSTANT_S_M
            * room.volumen
            / (-room.superficie_total * math.log1p(-mean_absorption))
        )
    coefficient = _resolve_air_attenuation(
        room,
        banda,
        environment=environment,
        include_air_attenuation=include_air_attenuation,
        air_attenuation_m_inv=air_attenuation_m_inv,
    )
    return _apply_air_attenuation(surface_rt, room, coefficient)


def rt60_millington(
    room: Room,
    banda: str,
    *,
    environment: Environment | None = None,
    include_air_attenuation: bool = False,
    air_attenuation_m_inv: float | None = None,
) -> float:
    _validate_band(banda)
    terms: list[float] = []
    for surface in room.superficies:
        alpha = surface.material.alpha_at(banda)
        if alpha >= 1.0:
            terms.append(math.inf)
        elif alpha <= 0.0:
            terms.append(0.0)
        else:
            terms.append(-surface.area * math.log1p(-alpha))
    absorption = sum(terms)
    if math.isinf(absorption):
        surface_rt = 0.0
    elif absorption <= 0.0:
        surface_rt = math.inf
    else:
        surface_rt = SABINE_CONSTANT_S_M * room.volumen / absorption
    coefficient = _resolve_air_attenuation(
        room,
        banda,
        environment=environment,
        include_air_attenuation=include_air_attenuation,
        air_attenuation_m_inv=air_attenuation_m_inv,
    )
    return _apply_air_attenuation(surface_rt, room, coefficient)


def _directional_absorption(room: Room, banda: str, first: int, second: int) -> tuple[float, float]:
    surfaces = (room.superficies[first], room.superficies[second])
    area = sum(surface.area for surface in surfaces)
    absorption = sum(
        surface.area * surface.material.alpha_at(banda) for surface in surfaces
    )
    return area, absorption / area


def rt60_fitzroy(
    room: Room,
    banda: str,
    *,
    environment: Environment | None = None,
    include_air_attenuation: bool = False,
    air_attenuation_m_inv: float | None = None,
) -> float:
    _validate_band(banda)

    directional = (
        _directional_absorption(room, banda, 0, 1),
        _directional_absorption(room, banda, 2, 3),
        _directional_absorption(room, banda, 4, 5),
    )
    terms: list[float] = []
    for area, alpha in directional:
        if alpha >= 1.0:
            terms.append(0.0)
        elif alpha <= 0.0:
            terms.append(math.inf)
        else:
            terms.append(area / -math.log1p(-alpha))

    if any(math.isinf(term) for term in terms):
        surface_rt = math.inf
    else:
        surface_rt = (
            SABINE_CONSTANT_S_M
            * room.volumen
            * sum(terms)
            / room.superficie_total**2
        )
    coefficient = _resolve_air_attenuation(
        room,
        banda,
        environment=environment,
        include_air_attenuation=include_air_attenuation,
        air_attenuation_m_inv=air_attenuation_m_inv,
    )
    return _apply_air_attenuation(surface_rt, room, coefficient)


_METHODS = (
    ("Sabine", rt60_sabine),
    ("Eyring", rt60_eyring),
    ("Millington", rt60_millington),
    ("FitzRoy", rt60_fitzroy),
)


def calculate_rt60_result(
    room: Room,
    *,
    environment: Environment | None = None,
    include_air_attenuation: bool = False,
) -> ReverberationResult:
    estimates: list[RT60Estimate] = []
    for banda in BANDAS_OCTAVA:
        mean_absorption = _a_promedio(room, banda)
        sabine_message = _sabine_warning(room, banda)
        for method_name, method in _METHODS:
            if method_name == "Sabine":
                value = method(
                    room,
                    banda,
                    environment=environment,
                    include_air_attenuation=include_air_attenuation,
                    warn=False,
                )
            else:
                value = method(
                    room,
                    banda,
                    environment=environment,
                    include_air_attenuation=include_air_attenuation,
                )
            estimate_warnings: list[str] = []
            if method_name == "Sabine" and sabine_message is not None:
                estimate_warnings.append(sabine_message)
            if not math.isfinite(value):
                estimate_warnings.append(
                    f"{method_name} RT60 at {banda} Hz is unbounded because total decay is zero."
                )
                value_or_none = None
            else:
                value_or_none = value
            estimates.append(
                RT60Estimate(
                    method=method_name,
                    band=banda,
                    value_seconds=value_or_none,
                    mean_absorption=mean_absorption,
                    warnings=tuple(estimate_warnings),
                )
            )
    return ReverberationResult(tuple(estimates))


calculate_rt60_detailed = calculate_rt60_result


def calculate_rt60(
    room: Room,
    *,
    environment: Environment | None = None,
    include_air_attenuation: bool = False,
) -> dict[str, dict[str, float]]:
    result = calculate_rt60_result(
        room,
        environment=environment,
        include_air_attenuation=include_air_attenuation,
    )
    for message in result.warnings:
        warning_type = (
            SabineApplicabilityWarning
            if message.startswith("Sabine at")
            else RuntimeWarning
        )
        warnings.warn(message, warning_type, stacklevel=2)
    return result.as_legacy_dict()


def rt60_promedio_sabine(
    room: Room,
    *,
    environment: Environment | None = None,
    include_air_attenuation: bool = False,
) -> float:
    per_surface_mean = []
    for surface in room.superficies:
        alpha = surface.material.alpha
        per_surface_mean.append(
            sum(alpha[banda] for banda in BANDAS_OCTAVA) / len(BANDAS_OCTAVA)
        )
    total_absorption = sum(
        surface.area * per_surface_mean[index]
        for index, surface in enumerate(room.superficies)
    )
    surface_rt = (
        math.inf
        if total_absorption <= 0.0
        else SABINE_CONSTANT_S_M * room.volumen / total_absorption
    )
    if include_air_attenuation:
        atmosphere = environment or room.environment
        coefficient = sum(
            atmosphere.air_attenuation_m_inv(float(banda)) for banda in BANDAS_OCTAVA
        ) / len(BANDAS_OCTAVA)
        surface_rt = _apply_air_attenuation(surface_rt, room, coefficient)
    if not math.isfinite(surface_rt):
        warnings.warn(
            "Mean Sabine RT60 is unbounded; returning RT60_UNBOUNDED_SENTINEL.",
            RuntimeWarning,
            stacklevel=2,
        )
        return RT60_UNBOUNDED_SENTINEL
    return surface_rt

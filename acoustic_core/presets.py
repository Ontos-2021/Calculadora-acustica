"""Representative material presets and treatment-related environmental loads.

The catalog values are screening data, not product declarations.  Functions
that mirror a published standard expose that distinction in their diagnostics;
none of the results in this module constitute testing or certification.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import math

from .environment import Environment, REFERENCE_PRESSURE_PA
from .models import BANDAS_OCTAVA, Material
from .uncertainty import Uncertainty


ISO11654_BANDS = ("250", "500", "1000", "2000", "4000")
ISO11654_REFERENCE_CURVE = {
    "250": 0.80,
    "500": 1.00,
    "1000": 1.00,
    "2000": 1.00,
    "4000": 0.90,
}
ISO11654_MAX_UNFAVORABLE_DEVIATION = 0.10
ISO11654_IMPLEMENTATION_NOTE = (
    "Engineering implementation of the public ISO 11654 reference-curve "
    "shifting procedure; requires practical absorption coefficients and is "
    "not a laboratory classification or certification."
)


@dataclass(frozen=True, slots=True)
class ISO11654Diagnostics:
    """Transparent result of the ISO 11654 public-reference procedure."""

    alpha_w: float
    iso_class: str
    practical_coefficients: dict[str, float]
    shifted_reference_curve: dict[str, float]
    unfavorable_deviations: dict[str, float]
    unfavorable_deviation_sum: float
    shape_indicators: tuple[str, ...]
    designation: str
    inferred_bands: tuple[str, ...]
    implementation_note: str = ISO11654_IMPLEMENTATION_NOTE

    def as_dict(self) -> dict:
        return {
            "alpha_w": self.alpha_w,
            "iso_class": self.iso_class,
            "practical_coefficients": dict(self.practical_coefficients),
            "shifted_reference_curve": dict(self.shifted_reference_curve),
            "unfavorable_deviations": dict(self.unfavorable_deviations),
            "unfavorable_deviation_sum": self.unfavorable_deviation_sum,
            "shape_indicators": list(self.shape_indicators),
            "designation": self.designation,
            "inferred_bands": list(self.inferred_bands),
            "implementation_note": self.implementation_note,
        }


def _iso_class(alpha_w: float) -> str:
    if alpha_w >= 0.90:
        return "A"
    if alpha_w >= 0.80:
        return "B"
    if alpha_w >= 0.60:
        return "C"
    if alpha_w >= 0.30:
        return "D"
    if alpha_w >= 0.15:
        return "E"
    return "No clasificado"


def _coefficient_at(alphas: Mapping[str | int | float, float], band: str) -> float | None:
    for key in (band, int(band), float(band)):
        if key in alphas:
            value = alphas[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(f"alpha_p at {band} Hz must be a real number")
            coefficient = float(value)
            if not math.isfinite(coefficient) or not 0.0 <= coefficient <= 1.0:
                raise ValueError(f"alpha_p at {band} Hz must be finite and in [0, 1]")
            return coefficient
    return None


def iso11654_diagnostics(
    alphas: Mapping[str | int | float, float],
    *,
    allow_legacy_4000_inference: bool = False,
) -> ISO11654Diagnostics:
    """Rate five practical coefficients by shifting the ISO reference curve.

    The curve starts at ``alpha_w=1.00`` and is shifted down in 0.05 steps.
    The highest position whose summed unfavorable deviations do not exceed
    0.10 is retained.  Shape indicators use the public 0.25 excess criterion.

    ``allow_legacy_4000_inference`` exists only for the historical four-band
    wrapper.  New callers should always supply all five practical coefficients.
    """

    if not isinstance(alphas, Mapping):
        raise TypeError("alphas must be a mapping of practical coefficients")
    practical: dict[str, float] = {}
    inferred: list[str] = []
    for band in ISO11654_BANDS:
        value = _coefficient_at(alphas, band)
        if value is None and band == "4000" and allow_legacy_4000_inference:
            value = practical.get("2000")
            if value is not None:
                inferred.append(band)
        if value is None:
            raise ValueError(
                "ISO 11654 rating requires practical coefficients at "
                + ", ".join(f"{item} Hz" for item in ISO11654_BANDS)
            )
        practical[band] = value

    accepted_curve: dict[str, float] | None = None
    accepted_deviations: dict[str, float] | None = None
    accepted_sum = 0.0
    alpha_w = 0.0
    for step in range(20, -1, -1):
        candidate = step * 0.05
        shift = candidate - 1.0
        curve = {
            band: round(max(0.0, base + shift), 2)
            for band, base in ISO11654_REFERENCE_CURVE.items()
        }
        deviations = {
            band: max(0.0, curve[band] - practical[band])
            for band in ISO11654_BANDS
        }
        deviation_sum = sum(deviations.values())
        if deviation_sum <= ISO11654_MAX_UNFAVORABLE_DEVIATION + 1e-12:
            alpha_w = round(candidate, 2)
            accepted_curve = curve
            accepted_deviations = deviations
            accepted_sum = deviation_sum
            break

    if accepted_curve is None or accepted_deviations is None:
        raise RuntimeError("the zero ISO 11654 reference curve was not accepted")

    indicators: list[str] = []
    if practical["250"] - accepted_curve["250"] >= 0.25 - 1e-12:
        indicators.append("L")
    if any(
        practical[band] - accepted_curve[band] >= 0.25 - 1e-12
        for band in ("500", "1000")
    ):
        indicators.append("M")
    if any(
        practical[band] - accepted_curve[band] >= 0.25 - 1e-12
        for band in ("2000", "4000")
    ):
        indicators.append("H")

    indicator_text = "" if not indicators else f" ({''.join(indicators)})"
    return ISO11654Diagnostics(
        alpha_w=alpha_w,
        iso_class=_iso_class(alpha_w),
        practical_coefficients=practical,
        shifted_reference_curve=accepted_curve,
        unfavorable_deviations={
            band: round(value, 6) for band, value in accepted_deviations.items()
        },
        unfavorable_deviation_sum=round(accepted_sum, 6),
        shape_indicators=tuple(indicators),
        designation=f"alpha_w = {alpha_w:.2f}{indicator_text}",
        inferred_bands=tuple(inferred),
    )


def classify_iso11654(alphas: Mapping[str | int | float, float]) -> tuple[float, str]:
    """Legacy ``(alpha_w, class)`` wrapper.

    Historical callers supplied only 250--2000 Hz.  In that case 4000 Hz is
    explicitly inferred from 2000 Hz for compatibility; use
    :func:`iso11654_diagnostics` for a strict five-band result.
    """

    result = iso11654_diagnostics(alphas, allow_legacy_4000_inference=True)
    return result.alpha_w, result.iso_class


MATERIALES_PRESETS: dict[str, Material] = {}

_CAT: dict[str, list[dict]] = {
    "Mampostería": [
        {"nombre": "Concreto pulido", "alphas": {"125": 0.01, "250": 0.01, "500": 0.02, "1000": 0.02, "2000": 0.03, "4000": 0.03}},
        {"nombre": "Concreto sin pintar", "alphas": {"125": 0.01, "250": 0.02, "500": 0.04, "1000": 0.06, "2000": 0.08, "4000": 0.10}},
        {"nombre": "Ladrillo visto", "alphas": {"125": 0.03, "250": 0.03, "500": 0.04, "1000": 0.05, "2000": 0.06, "4000": 0.07}},
        {"nombre": "Ladrillo enlucido", "alphas": {"125": 0.02, "250": 0.02, "500": 0.03, "1000": 0.04, "2000": 0.05, "4000": 0.05}},
        {"nombre": "Bloque de hormigón hueco", "alphas": {"125": 0.05, "250": 0.04, "500": 0.03, "1000": 0.04, "2000": 0.05, "4000": 0.05}},
        {"nombre": "Piedra natural", "alphas": {"125": 0.01, "250": 0.01, "500": 0.02, "1000": 0.02, "2000": 0.03, "4000": 0.03}},
    ],
    "Madera": [
        {"nombre": "Madera contrachapada (10mm)", "alphas": {"125": 0.05, "250": 0.05, "500": 0.07, "1000": 0.06, "2000": 0.06, "4000": 0.07}},
        {"nombre": "Madera maciza (20mm)", "alphas": {"125": 0.05, "250": 0.04, "500": 0.04, "1000": 0.05, "2000": 0.05, "4000": 0.06}},
        {"nombre": "Parquet sobre hormigón", "alphas": {"125": 0.04, "250": 0.04, "500": 0.05, "1000": 0.05, "2000": 0.06, "4000": 0.06}},
        {"nombre": "Panel de madera perforado", "alphas": {"125": 0.15, "250": 0.25, "500": 0.40, "1000": 0.30, "2000": 0.20, "4000": 0.15}},
        {"nombre": "MDF (12mm)", "alphas": {"125": 0.05, "250": 0.05, "500": 0.06, "1000": 0.06, "2000": 0.06, "4000": 0.07}},
    ],
    "Pisos": [
        {"nombre": "Alfombra gruesa sobre espuma", "alphas": {"125": 0.08, "250": 0.24, "500": 0.57, "1000": 0.69, "2000": 0.71, "4000": 0.73}},
        {"nombre": "Alfombra sobre moqueta", "alphas": {"125": 0.05, "250": 0.10, "500": 0.25, "1000": 0.40, "2000": 0.50, "4000": 0.55}},
        {"nombre": "Alfombra fina sobre hormigón", "alphas": {"125": 0.02, "250": 0.06, "500": 0.14, "1000": 0.37, "2000": 0.48, "4000": 0.52}},
        {"nombre": "Linóleo sobre hormigón", "alphas": {"125": 0.02, "250": 0.03, "500": 0.03, "1000": 0.04, "2000": 0.04, "4000": 0.05}},
        {"nombre": "Baldosa vinílica", "alphas": {"125": 0.02, "250": 0.02, "500": 0.03, "1000": 0.03, "2000": 0.04, "4000": 0.04}},
        {"nombre": "Suelo de goma", "alphas": {"125": 0.04, "250": 0.04, "500": 0.08, "1000": 0.12, "2000": 0.10, "4000": 0.10}},
    ],
    "Techos": [
        {"nombre": "Escayola lisa", "alphas": {"125": 0.04, "250": 0.04, "500": 0.05, "1000": 0.06, "2000": 0.08, "4000": 0.08}},
        {"nombre": "Escayola acústica", "alphas": {"125": 0.10, "250": 0.15, "500": 0.30, "1000": 0.40, "2000": 0.35, "4000": 0.30}},
        {"nombre": "Falso techo mineral (suspendido)", "alphas": {"125": 0.15, "250": 0.40, "500": 0.70, "1000": 0.80, "2000": 0.75, "4000": 0.65}},
        {"nombre": "Panel metálico perforado", "alphas": {"125": 0.10, "250": 0.30, "500": 0.60, "1000": 0.65, "2000": 0.55, "4000": 0.45}},
    ],
    "Vidrio": [
        {"nombre": "Vidrio simple (3-6mm)", "alphas": {"125": 0.03, "250": 0.03, "500": 0.05, "1000": 0.08, "2000": 0.10, "4000": 0.10}},
        {"nombre": "Vidrio doble (4-12-4)", "alphas": {"125": 0.02, "250": 0.02, "500": 0.04, "1000": 0.05, "2000": 0.06, "4000": 0.06}},
        {"nombre": "Vidrio laminado", "alphas": {"125": 0.03, "250": 0.03, "500": 0.05, "1000": 0.07, "2000": 0.08, "4000": 0.08}},
        {"nombre": "Cristal blindado", "alphas": {"125": 0.02, "250": 0.02, "500": 0.03, "1000": 0.04, "2000": 0.05, "4000": 0.05}},
    ],
    "Telas y cortinas": [
        {"nombre": "Cortina ligera (plegada 50%)", "alphas": {"125": 0.05, "250": 0.12, "500": 0.20, "1000": 0.35, "2000": 0.45, "4000": 0.50}},
        {"nombre": "Cortina pesada (terciopelo)", "alphas": {"125": 0.10, "250": 0.30, "500": 0.50, "1000": 0.65, "2000": 0.70, "4000": 0.70}},
        {"nombre": "Cortina media (plegada 100%)", "alphas": {"125": 0.07, "250": 0.20, "500": 0.35, "1000": 0.50, "2000": 0.55, "4000": 0.55}},
        {"nombre": "Moqueta de lana (6mm)", "alphas": {"125": 0.08, "250": 0.10, "500": 0.25, "1000": 0.40, "2000": 0.45, "4000": 0.50}},
    ],
    "Paneles acústicos": [
        {"nombre": "Panel fibra de vidrio (50mm)", "alphas": {"125": 0.20, "250": 0.60, "500": 0.85, "1000": 0.90, "2000": 0.85, "4000": 0.80}},
        {"nombre": "Panel fibra de vidrio (25mm)", "alphas": {"125": 0.10, "250": 0.35, "500": 0.70, "1000": 0.85, "2000": 0.80, "4000": 0.75}},
        {"nombre": "Lana mineral (50mm)", "alphas": {"125": 0.25, "250": 0.55, "500": 0.75, "1000": 0.85, "2000": 0.80, "4000": 0.75}},
        {"nombre": "Lana mineral (100mm)", "alphas": {"125": 0.35, "250": 0.75, "500": 0.90, "1000": 0.95, "2000": 0.90, "4000": 0.85}},
        {"nombre": "Panel microperforado", "alphas": {"125": 0.15, "250": 0.40, "500": 0.70, "1000": 0.65, "2000": 0.50, "4000": 0.40}},
        {"nombre": "Panel de fibra de madera", "alphas": {"125": 0.20, "250": 0.50, "500": 0.75, "1000": 0.80, "2000": 0.75, "4000": 0.70}},
    ],
    "Espumas": [
        {"nombre": "Espuma de poliuretano (50mm)", "alphas": {"125": 0.15, "250": 0.35, "500": 0.65, "1000": 0.80, "2000": 0.80, "4000": 0.75}},
        {"nombre": "Espuma de melamina (50mm)", "alphas": {"125": 0.15, "250": 0.30, "500": 0.60, "1000": 0.80, "2000": 0.85, "4000": 0.80}},
        {"nombre": "Espuma de poliuretano (25mm)", "alphas": {"125": 0.10, "250": 0.20, "500": 0.45, "1000": 0.60, "2000": 0.65, "4000": 0.60}},
    ],
}


_OLD_NAMES = {
    "Concreto": "Concreto sin pintar",
    "Madera": "Madera contrachapada (10mm)",
    "Yeso": "Escayola lisa",
    "Vidrio": "Vidrio simple (3-6mm)",
    "Alfombra gruesa": "Alfombra gruesa sobre espuma",
    "Cortina pesada": "Cortina pesada (terciopelo)",
    "Panel acústico": "Panel fibra de vidrio (50mm)",
    "Espuma acústica": "Espuma de poliuretano (50mm)",
}


CATALOG_PROVENANCE = (
    "Representative architectural-acoustics table values retained as an "
    "engineering estimate; not traceable product test data and not suitable "
    "for compliance or certification."
)
CATALOG_UNCERTAINTY = Uncertainty(
    value=0.05,
    unit="absorption coefficient",
    coverage_factor=2.0,
    confidence_level=0.95,
    source=(
        "Assumed screening uncertainty for representative catalog data; "
        "not estimated from repeated laboratory measurements"
    ),
)
CATALOG_REFERENCES = (
    "ISO 11654:1997 public reference-curve rating method",
    "Representative public architectural-acoustics absorption tables",
)


@dataclass(frozen=True, slots=True)
class MaterialCatalogRecord:
    """Metadata kept beside a legacy :class:`Material` preset."""

    name: str
    category: str
    mounting_condition: str
    coefficient_basis: str
    data_status: str
    provenance: str
    uncertainty: Uncertainty
    thickness_m: float | None = None
    alias_of: str | None = None
    references: tuple[str, ...] = CATALOG_REFERENCES

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "mounting_condition": self.mounting_condition,
            "coefficient_basis": self.coefficient_basis,
            "data_status": self.data_status,
            "provenance": self.provenance,
            "uncertainty": {
                "standard": self.uncertainty.value,
                "expanded": self.uncertainty.expanded,
                "unit": self.uncertainty.unit,
                "coverage_factor": self.uncertainty.coverage_factor,
                "confidence_level": self.uncertainty.confidence_level,
                "source": self.uncertainty.source,
            },
            "thickness_m": self.thickness_m,
            "alias_of": self.alias_of,
            "references": list(self.references),
        }


_CATEGORY_MOUNTING = {
    "Mampostería": "Rigid continuous surface; direct/exposed finish",
    "Madera": "Rigid layer directly over a hard backing unless named otherwise",
    "Pisos": "Floor finish directly over the substrate stated in the name",
    "Techos": "Ceiling finish; no cavity unless suspended is stated in the name",
    "Vidrio": "Framed glazing; nominal incidence and frame details unspecified",
    "Telas y cortinas": "Free-hanging textile; pleating only where stated",
    "Paneles acústicos": "Direct-mounted porous panel; no air gap assumed",
    "Espumas": "Direct-mounted porous foam; no air gap assumed",
}
_MOUNTING_OVERRIDES = {
    "Panel de madera perforado": "Perforated wood facing; backing cavity and infill unspecified",
    "Falso techo mineral (suspendido)": "Suspended ceiling; plenum depth unspecified",
    "Panel metálico perforado": "Perforated metal facing; backing cavity and infill unspecified",
    "Panel microperforado": "Microperforated facing; backing cavity unspecified",
    "Alfombra gruesa sobre espuma": "Carpet over resilient foam underlay",
    "Alfombra sobre moqueta": "Carpet over textile underlay",
    "Cortina ligera (plegada 50%)": "Free-hanging curtain, nominal 50% fullness; airspace unspecified",
    "Cortina media (plegada 100%)": "Free-hanging curtain, nominal 100% fullness; airspace unspecified",
    "Cortina pesada (terciopelo)": "Free-hanging heavy curtain; fullness and airspace unspecified",
}


def _catalog_thickness(name: str) -> float | None:
    for millimetres in (100, 50, 25, 20, 12, 10, 6):
        if f"({millimetres}mm)" in name:
            return millimetres / 1000.0
    return None


def _mounting_condition(name: str, category: str) -> str:
    return _MOUNTING_OVERRIDES.get(name, _CATEGORY_MOUNTING[category])


MATERIAL_CATALOG_METADATA: dict[str, MaterialCatalogRecord] = {}
MATERIAL_RECORDS = MATERIAL_CATALOG_METADATA


for _cat_name, _entries in _CAT.items():
    for _e in _entries:
        name = _e["nombre"]
        rating = iso11654_diagnostics(_e["alphas"])
        MAT = Material(
            nombre=name,
            alphas=_e["alphas"],
            categoria=_cat_name,
            alpha_w=rating.alpha_w,
            iso_class=rating.iso_class,
            provenance=CATALOG_PROVENANCE,
            uncertainty=CATALOG_UNCERTAINTY,
        )
        MATERIALES_PRESETS[name] = MAT
        MATERIAL_CATALOG_METADATA[name] = MaterialCatalogRecord(
            name=name,
            category=_cat_name,
            mounting_condition=_mounting_condition(name, _cat_name),
            coefficient_basis="representative octave-band absorption coefficients",
            data_status="engineering_estimate_not_product_test",
            provenance=CATALOG_PROVENANCE,
            uncertainty=CATALOG_UNCERTAINTY,
            thickness_m=_catalog_thickness(name),
        )

for _old, _new in _OLD_NAMES.items():
    if _new in MATERIALES_PRESETS:
        src = MATERIALES_PRESETS[_new]
        old_mat = Material(
            nombre=_old,
            alphas=dict(src.alphas),
            categoria=src.categoria,
            alpha_w=src.alpha_w,
            iso_class=src.iso_class,
            provenance=src.provenance,
            uncertainty=src.uncertainty,
        )
        MATERIALES_PRESETS[_old] = old_mat
        source_record = MATERIAL_CATALOG_METADATA[_new]
        MATERIAL_CATALOG_METADATA[_old] = MaterialCatalogRecord(
            name=_old,
            category=source_record.category,
            mounting_condition=source_record.mounting_condition,
            coefficient_basis=source_record.coefficient_basis,
            data_status=source_record.data_status,
            provenance=source_record.provenance,
            uncertainty=source_record.uncertainty,
            thickness_m=source_record.thickness_m,
            alias_of=_new,
            references=source_record.references,
        )


CATEGORIAS: dict[str, list[str]] = {}
for name, mat in MATERIALES_PRESETS.items():
    CATEGORIAS.setdefault(mat.categoria, []).append(name)


def get_material_metadata(name: str) -> MaterialCatalogRecord:
    """Return catalog metadata while leaving ``MATERIALES_PRESETS`` unchanged."""

    try:
        return MATERIAL_CATALOG_METADATA[name]
    except KeyError as exc:
        raise KeyError(f"Unknown material preset: {name}") from exc


def material_catalog_records(*, include_aliases: bool = True) -> list[dict]:
    """Return JSON-friendly catalog records for a future API integration."""

    return [
        record.as_dict()
        for record in MATERIAL_CATALOG_METADATA.values()
        if include_aliases or record.alias_of is None
    ]


def search_materials(
    query: str = "",
    categoria: str = "",
    min_alpha_w: float = 0.0,
    max_alpha_w: float = 1.0,
    iso_class: str = "",
) -> list[Material]:
    results = []
    for mat in MATERIALES_PRESETS.values():
        if categoria and mat.categoria != categoria:
            continue
        if mat.alpha_w is not None and (mat.alpha_w < min_alpha_w or mat.alpha_w > max_alpha_w):
            continue
        if iso_class and mat.iso_class != iso_class:
            continue
        if query and query.lower() not in mat.nombre.lower():
            continue
        results.append(mat)
    return results


AIR_ATTENUATION_IMPLEMENTATION_NOTE = (
    "ISO 9613-1 atmospheric attenuation equation as an engineering public-"
    "reference implementation; not a certified propagation calculation."
)


@dataclass(frozen=True, slots=True)
class AirAttenuationResult:
    frequency_hz: float
    temperature_c: float
    relative_humidity_percent: float
    pressure_pa: float
    distance_m: float
    attenuation_db_per_m: float
    amplitude_attenuation_np_per_m: float
    energy_decay_m_inv: float
    attenuation_db: float
    energy_ratio: float
    implementation_note: str = AIR_ATTENUATION_IMPLEMENTATION_NOTE

    def as_dict(self) -> dict:
        return {
            "frequency_hz": self.frequency_hz,
            "temperature_c": self.temperature_c,
            "relative_humidity_percent": self.relative_humidity_percent,
            "pressure_pa": self.pressure_pa,
            "distance_m": self.distance_m,
            "attenuation_db_per_m": self.attenuation_db_per_m,
            "amplitude_attenuation_np_per_m": self.amplitude_attenuation_np_per_m,
            "energy_decay_m_inv": self.energy_decay_m_inv,
            "attenuation_db": self.attenuation_db,
            "energy_ratio": self.energy_ratio,
            "implementation_note": self.implementation_note,
        }


def calculate_air_attenuation(
    frequency_hz: float,
    humidity_percent: float = 50.0,
    temp_celsius: float = 20.0,
    *,
    pressure_pa: float = REFERENCE_PRESSURE_PA,
    distance_m: float = 1.0,
) -> AirAttenuationResult:
    """Return atmospheric attenuation with explicit propagation/decay units."""

    if isinstance(distance_m, bool) or not isinstance(distance_m, (int, float)):
        raise TypeError("distance_m must be a real number")
    distance = float(distance_m)
    if not math.isfinite(distance) or distance < 0.0:
        raise ValueError("distance_m must be finite and non-negative")
    environment = Environment(
        temperature_c=temp_celsius,
        relative_humidity=humidity_percent,
        pressure_pa=pressure_pa,
    )
    attenuation_db_per_m = environment.air_attenuation_db_per_m(frequency_hz)
    amplitude_np_per_m = attenuation_db_per_m * math.log(10.0) / 20.0
    energy_decay_m_inv = environment.air_attenuation_m_inv(frequency_hz)
    attenuation_db = attenuation_db_per_m * distance
    return AirAttenuationResult(
        frequency_hz=float(frequency_hz),
        temperature_c=environment.temperature_c,
        relative_humidity_percent=environment.relative_humidity,
        pressure_pa=environment.pressure_pa,
        distance_m=distance,
        attenuation_db_per_m=attenuation_db_per_m,
        amplitude_attenuation_np_per_m=amplitude_np_per_m,
        energy_decay_m_inv=energy_decay_m_inv,
        attenuation_db=attenuation_db,
        energy_ratio=10.0 ** (-attenuation_db / 10.0),
    )


def calculate_air_absorption(
    frequency_hz: float,
    humidity_percent: float = 50.0,
    temp_celsius: float = 20.0,
) -> float:
    """Legacy scalar: return energy-decay attenuation ``m`` in inverse metres.

    This coefficient is suitable for the ``4 m V`` room-decay term.  Use
    :func:`calculate_air_attenuation` when propagation dB/m is required.
    """

    return calculate_air_attenuation(
        frequency_hz,
        humidity_percent,
        temp_celsius,
    ).energy_decay_m_inv


AIR_ABSORPTION_DEFAULT = {
    b: calculate_air_absorption(float(b), 50.0, 20.0) for b in BANDAS_OCTAVA
}


@dataclass(frozen=True, slots=True)
class AudienceConfig:
    num_people: int = 0
    seated: bool = True
    upholstered: bool = True
    occupied: float = 0.85

    def __post_init__(self) -> None:
        if (
            isinstance(self.num_people, bool)
            or not isinstance(self.num_people, int)
            or self.num_people < 0
        ):
            raise ValueError("num_people must be a non-negative integer")
        if not isinstance(self.seated, bool) or not isinstance(self.upholstered, bool):
            raise TypeError("seated and upholstered must be booleans")
        if isinstance(self.occupied, bool) or not isinstance(self.occupied, (int, float)):
            raise TypeError("occupied must be a real fraction")
        occupied = float(self.occupied)
        if not math.isfinite(occupied) or not 0.0 <= occupied <= 1.0:
            raise ValueError("occupied must be between 0 and 1")
        object.__setattr__(self, "occupied", occupied)


AUDIENCE_ABSORPTION_PER_PERSON: dict[str, float] = {
    "125": 0.20, "250": 0.30, "500": 0.40, "1000": 0.45, "2000": 0.50, "4000": 0.45,
}
AUDIENCE_ABSORPTION_SEATED_UNUPHOLSTERED: dict[str, float] = {
    "125": 0.16, "250": 0.24, "500": 0.34, "1000": 0.39, "2000": 0.43, "4000": 0.39,
}
AUDIENCE_ABSORPTION_STANDING: dict[str, float] = {
    "125": 0.10, "250": 0.20, "500": 0.30, "1000": 0.35, "2000": 0.40, "4000": 0.35,
}
EMPTY_SEAT_ABSORPTION: dict[str, float] = {
    "125": 0.10, "250": 0.15, "500": 0.20, "1000": 0.25, "2000": 0.25, "4000": 0.25,
}
EMPTY_SEAT_ABSORPTION_UNUPHOLSTERED: dict[str, float] = {
    "125": 0.02, "250": 0.03, "500": 0.04, "1000": 0.05, "2000": 0.05, "4000": 0.05,
}


@dataclass(frozen=True, slots=True)
class AudienceAbsorptionResult:
    equivalent_absorption_area_m2_sabins: dict[str, float]
    occupied_people_equivalent: float
    empty_seats_equivalent: float
    occupied_absorption_per_person_m2: dict[str, float]
    empty_seat_absorption_m2: dict[str, float]
    assumptions: tuple[str, ...]
    estimate_label: str = "engineering_estimate_not_measurement"

    def as_dict(self) -> dict:
        return {
            "equivalent_absorption_area_m2_sabins": dict(
                self.equivalent_absorption_area_m2_sabins
            ),
            "occupied_people_equivalent": self.occupied_people_equivalent,
            "empty_seats_equivalent": self.empty_seats_equivalent,
            "occupied_absorption_per_person_m2": dict(
                self.occupied_absorption_per_person_m2
            ),
            "empty_seat_absorption_m2": dict(self.empty_seat_absorption_m2),
            "assumptions": list(self.assumptions),
            "estimate_label": self.estimate_label,
        }


def audience_absorption_result(config: AudienceConfig) -> AudienceAbsorptionResult:
    """Estimate audience equivalent absorption area and expose assumptions."""

    if not isinstance(config, AudienceConfig):
        raise TypeError("config must be an AudienceConfig")

    if config.seated:
        occupied_curve = (
            AUDIENCE_ABSORPTION_PER_PERSON
            if config.upholstered
            else AUDIENCE_ABSORPTION_SEATED_UNUPHOLSTERED
        )
        empty_curve = (
            EMPTY_SEAT_ABSORPTION
            if config.upholstered
            else EMPTY_SEAT_ABSORPTION_UNUPHOLSTERED
        )
        occupied_people = config.num_people * config.occupied
        empty_seats = config.num_people - occupied_people
        seat_assumption = (
            "Occupied and empty upholstered-chair screening curves are used."
            if config.upholstered
            else "Occupied and empty hard-chair screening curves are used."
        )
    else:
        occupied_curve = AUDIENCE_ABSORPTION_STANDING
        empty_curve = {band: 0.0 for band in BANDAS_OCTAVA}
        occupied_people = config.num_people * config.occupied
        empty_seats = 0.0
        seat_assumption = (
            "Standing layout has no empty-seat absorption; upholstered is ignored."
        )

    total = {
        band: round(
            occupied_curve[band] * occupied_people + empty_curve[band] * empty_seats,
            3,
        )
        for band in BANDAS_OCTAVA
    }
    return AudienceAbsorptionResult(
        equivalent_absorption_area_m2_sabins=total,
        occupied_people_equivalent=round(occupied_people, 3),
        empty_seats_equivalent=round(empty_seats, 3),
        occupied_absorption_per_person_m2=dict(occupied_curve),
        empty_seat_absorption_m2=dict(empty_curve),
        assumptions=(
            "num_people is capacity/population and occupied is its expected occupied fraction.",
            "Values are equivalent absorption area per person or seat, not coefficients.",
            seat_assumption,
            "Representative screening curves are not venue-specific measurements.",
        ),
    )


def calculate_audience_absorption(config: AudienceConfig) -> dict[str, float]:
    """Legacy spectrum-only wrapper around :func:`audience_absorption_result`."""

    return audience_absorption_result(config).equivalent_absorption_area_m2_sabins

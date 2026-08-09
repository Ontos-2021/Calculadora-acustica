"""Engineering calculations for airborne sound isolation and room noise.

The contour calculations in this module implement the publicly documented
procedures and tabulated data identified in :data:`ENGINEERING_REFERENCES`.
They do not replace a licensed standard, an accredited laboratory test, or an
acoustician's project-specific assessment.  The panel, duct, and flanking
functions are deliberately labelled as engineering estimates.

Legacy callers still receive the six project octave bands by default.  A
caller can request any positive frequency grid with ``frequencies_hz``.  STC,
Rw, NC, and NR require their complete standard band sets; the old six-octave
input is accepted only as a clearly flagged interpolation estimate.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from decimal import Decimal, ROUND_HALF_UP

from .models import BANDAS_OCTAVA


SPEED_OF_SOUND_M_S = 343.0
AIR_DENSITY_KG_M3 = 1.21
C = SPEED_OF_SOUND_M_S  # Backwards-compatible name.

OCTAVE_BANDS_HZ = tuple(int(band) for band in BANDAS_OCTAVA)
STC_BANDS_HZ = (
    125, 160, 200, 250, 315, 400, 500, 630,
    800, 1000, 1250, 1600, 2000, 2500, 3150, 4000,
)
ISO717_BANDS_HZ = (
    100, 125, 160, 200, 250, 315, 400, 500,
    630, 800, 1000, 1250, 1600, 2000, 2500, 3150,
)
THIRD_OCTAVE_BANDS_HZ = tuple(sorted(set(STC_BANDS_HZ) | set(ISO717_BANDS_HZ)))

# Public aliases use both English and the naming style already used by the app.
STC_FREQUENCIES = STC_BANDS_HZ
STC_BANDS = STC_BANDS_HZ
RW_BANDS_HZ = ISO717_BANDS_HZ
RW_FREQUENCIES = ISO717_BANDS_HZ
RW_BANDS = ISO717_BANDS_HZ
ISO717_BANDS = ISO717_BANDS_HZ
ONE_THIRD_OCTAVE_BANDS_HZ = THIRD_OCTAVE_BANDS_HZ
BANDAS_TERCIO_OCTAVA = [str(frequency) for frequency in THIRD_OCTAVE_BANDS_HZ]
BANDAS_TERCIO_OCTAVA_STC = [str(frequency) for frequency in STC_BANDS_HZ]
BANDAS_TERCIO_OCTAVA_RW = [str(frequency) for frequency in ISO717_BANDS_HZ]

ENGINEERING_REFERENCES = {
    "astm_e413": (
        "ASTM E413-22 public scope and ISO comparison note: "
        "https://www.astm.org/e0413-22.html"
    ),
    "stc_contour": (
        "Public E413 contour description and offsets: "
        "https://freeacoustics.tools/stc.html"
    ),
    "iso_717": (
        "ISO 717-1:2020 public catalogue and scope: "
        "https://www.iso.org/standard/77435.html"
    ),
    "iso_rating": (
        "Public ISO 717-1 contour procedure: "
        "https://en.wikipedia.org/wiki/Sound_reduction_index"
    ),
    "iso_spectra": (
        "Public explanation and table of C/Ctr spectra: "
        "https://ateliercrescendo.ac/understanding-correction-terms-like-ctr-c-etc-in-building-acoustics/"
    ),
    "nc": "https://www.engineeringtoolbox.com/nc-noise-criterion-d_725.html",
    "nr": "https://www.engineeringtoolbox.com/nr-noise-rating-d_60.html",
    "coincidence": (
        "Plate coincidence derivation: "
        "https://euphonics.org/4-3-3-the-critical-frequency-of-a-vibrating-plate/"
    ),
    "mass_air_mass": (
        "Public mass-air-mass formula and limiting behaviour: "
        "https://visual-acoustic.com/calculators/transmission-loss/"
    ),
    "lined_duct": (
        "Public Sabine lined-duct formula: "
        "https://novasolver.jp/en/tools/duct-silencer-attenuation.html"
    ),
    "iso_12354_scope": (
        "ISO 12354-1 public scope: "
        "https://www.iso.org/standard/70242.html"
    ),
}


def _as_finite(value: float, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _positive(value: float, name: str) -> float:
    number = _as_finite(value, name)
    if number <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return number


def _fraction(value: float, name: str, *, zero_allowed: bool = True) -> float:
    number = _as_finite(value, name)
    if number < 0.0 or number > 1.0 or (not zero_allowed and number == 0.0):
        comparator = "0 < value <= 1" if not zero_allowed else "0 <= value <= 1"
        raise ValueError(f"{name} must satisfy {comparator}")
    return number


def _round_half_up(value: float, digits: int = 0) -> int | float:
    quantum = Decimal("1").scaleb(-digits)
    rounded = Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP)
    return int(rounded) if digits == 0 else float(rounded)


def _band_key(frequency_hz: float) -> str:
    if float(frequency_hz).is_integer():
        return str(int(frequency_hz))
    return f"{frequency_hz:g}"


def _frequency_grid(frequencies_hz: Iterable[float] | None) -> tuple[float, ...]:
    source = OCTAVE_BANDS_HZ if frequencies_hz is None else frequencies_hz
    frequencies = tuple(_positive(frequency, "frequency_hz") for frequency in source)
    if not frequencies:
        raise ValueError("frequencies_hz must contain at least one frequency")
    if len(set(frequencies)) != len(frequencies):
        raise ValueError("frequencies_hz must not contain duplicates")
    return frequencies


def _mass_law_raw(mass_per_area_kgm2: float, frequency_hz: float) -> float:
    mass = _positive(mass_per_area_kgm2, "mass_per_area_kgm2")
    frequency = _positive(frequency_hz, "frequency_hz")
    return max(0.0, 20.0 * (math.log10(mass) + math.log10(frequency)) - 47.0)


def mass_law_tl(mass_per_area_kgm2: float, frequency_hz: float) -> float:
    """Return the random-incidence mass-law asymptote in dB.

    ``TL = 20 log10(m' f) - 47`` assumes an infinite, limp, airtight,
    homogeneous leaf away from panel resonances and coincidence.  It is an
    engineering asymptote, not a tested rating.
    """

    return round(_mass_law_raw(mass_per_area_kgm2, frequency_hz), 1)


MATERIAL_C_L: dict[str, float] = {
    "concreto": 3500,
    "yeso": 1700,
    "madera": 3200,
    "acero": 5200,
    "vidrio": 5200,
    "ladrillo": 3000,
    "aluminio": 5100,
    "fibrocemento": 2500,
}

# Representative isotropic properties for early design only.  Real products,
# masonry, timber grain direction, laminates, and moisture state can differ.
MATERIAL_PROPERTIES: dict[str, dict[str, float]] = {
    "concreto": {
        "density_kgm3": 2400.0,
        "young_modulus_pa": 30.0e9,
        "poisson_ratio": 0.20,
        "loss_factor": 0.020,
    },
    "yeso": {
        "density_kgm3": 800.0,
        "young_modulus_pa": 2.5e9,
        "poisson_ratio": 0.30,
        "loss_factor": 0.030,
    },
    "madera": {
        "density_kgm3": 600.0,
        "young_modulus_pa": 10.0e9,
        "poisson_ratio": 0.30,
        "loss_factor": 0.020,
    },
    "acero": {
        "density_kgm3": 7850.0,
        "young_modulus_pa": 200.0e9,
        "poisson_ratio": 0.30,
        "loss_factor": 0.002,
    },
    "vidrio": {
        "density_kgm3": 2500.0,
        "young_modulus_pa": 70.0e9,
        "poisson_ratio": 0.23,
        "loss_factor": 0.004,
    },
    "ladrillo": {
        "density_kgm3": 1800.0,
        "young_modulus_pa": 15.0e9,
        "poisson_ratio": 0.20,
        "loss_factor": 0.020,
    },
    "aluminio": {
        "density_kgm3": 2700.0,
        "young_modulus_pa": 69.0e9,
        "poisson_ratio": 0.33,
        "loss_factor": 0.002,
    },
    "fibrocemento": {
        "density_kgm3": 1500.0,
        "young_modulus_pa": 12.0e9,
        "poisson_ratio": 0.25,
        "loss_factor": 0.020,
    },
}


def plate_critical_frequency(
    thickness_m: float,
    density_kgm3: float,
    young_modulus_pa: float,
    poisson_ratio: float,
    *,
    speed_of_sound_m_s: float = SPEED_OF_SOUND_M_S,
) -> float:
    """Return the thin isotropic plate critical frequency in Hz.

    The calculation uses ``D = E h^3 / (12 (1-v^2))`` and
    ``fc = c^2/(2*pi) * sqrt(rho*h/D)``.  Panel dimensions and boundary
    conditions, which control low-frequency modal resonances, are not known.
    """

    thickness = _positive(thickness_m, "thickness_m")
    density = _positive(density_kgm3, "density_kgm3")
    young_modulus = _positive(young_modulus_pa, "young_modulus_pa")
    poisson = _as_finite(poisson_ratio, "poisson_ratio")
    speed = _positive(speed_of_sound_m_s, "speed_of_sound_m_s")
    if not -1.0 < poisson < 0.5:
        raise ValueError("poisson_ratio must satisfy -1 < value < 0.5")

    bending_stiffness = (
        young_modulus * thickness**3 / (12.0 * (1.0 - poisson**2))
    )
    critical = speed**2 / (2.0 * math.pi) * math.sqrt(
        density * thickness / bending_stiffness
    )
    return round(critical, 1)


def critical_frequency(
    thickness_m: float,
    c_l_material: float = 3500.0,
    *,
    density_kgm3: float | None = None,
    young_modulus_pa: float | None = None,
    poisson_ratio: float | None = None,
) -> float:
    """Return panel critical frequency, retaining the legacy wave-speed API.

    Supply all three plate properties to use the thin-plate expression.
    Otherwise the legacy empirical relation ``c^2/(1.8*c_l*h)`` is used.
    """

    supplied = (density_kgm3, young_modulus_pa, poisson_ratio)
    if any(value is not None for value in supplied):
        if not all(value is not None for value in supplied):
            raise ValueError(
                "density_kgm3, young_modulus_pa, and poisson_ratio must be supplied together"
            )
        return plate_critical_frequency(
            thickness_m,
            density_kgm3,  # type: ignore[arg-type]
            young_modulus_pa,  # type: ignore[arg-type]
            poisson_ratio,  # type: ignore[arg-type]
        )

    thickness = _positive(thickness_m, "thickness_m")
    longitudinal_speed = _positive(c_l_material, "c_l_material")
    return round(C**2 / (1.8 * longitudinal_speed * thickness), 1)


def coincidence_notch(
    frequency_hz: float,
    fc: float,
    depth_db: float = 10.0,
    *,
    width_octaves: float = 0.5,
) -> float:
    """Return a smooth, finite coincidence correction for an estimate.

    ``depth_db`` is normally derived from material loss factor by
    :func:`single_panel_tl_details`.  The Gaussian in log-frequency is a
    diffuse-band smoothing assumption, not a standardized prediction method.
    """

    frequency = _positive(frequency_hz, "frequency_hz")
    if fc == float("inf"):
        return 0.0
    critical = _positive(fc, "fc")
    depth = _as_finite(depth_db, "depth_db")
    width = _positive(width_octaves, "width_octaves")
    if depth < 0:
        raise ValueError("depth_db must be non-negative")
    ratio_octaves = math.log2(frequency / critical)
    return round(depth * math.exp(-0.5 * (ratio_octaves / width) ** 2), 1)


def _single_panel_properties(
    material_type: str,
    density_kgm3: float | None,
    young_modulus_pa: float | None,
    poisson_ratio: float | None,
    loss_factor: float | None,
) -> tuple[dict[str, float], bool]:
    fallback_used = material_type not in MATERIAL_PROPERTIES
    properties = dict(MATERIAL_PROPERTIES.get(material_type, MATERIAL_PROPERTIES["concreto"]))
    overrides = {
        "density_kgm3": density_kgm3,
        "young_modulus_pa": young_modulus_pa,
        "poisson_ratio": poisson_ratio,
        "loss_factor": loss_factor,
    }
    for name, value in overrides.items():
        if value is not None:
            properties[name] = float(value)

    properties["density_kgm3"] = _positive(properties["density_kgm3"], "density_kgm3")
    properties["young_modulus_pa"] = _positive(
        properties["young_modulus_pa"], "young_modulus_pa"
    )
    poisson = _as_finite(properties["poisson_ratio"], "poisson_ratio")
    if not -1.0 < poisson < 0.5:
        raise ValueError("poisson_ratio must satisfy -1 < value < 0.5")
    properties["poisson_ratio"] = poisson
    properties["loss_factor"] = _fraction(
        properties["loss_factor"], "loss_factor", zero_allowed=False
    )
    return properties, fallback_used


def single_panel_tl_details(
    mass_per_area_kgm2: float,
    thickness_m: float,
    material_type: str = "concreto",
    *,
    density_kgm3: float | None = None,
    young_modulus_pa: float | None = None,
    poisson_ratio: float | None = None,
    loss_factor: float | None = None,
    frequencies_hz: Iterable[float] | None = None,
) -> dict:
    """Estimate a homogeneous single panel and return model diagnostics.

    Mass law supplies the asymptote.  Thin isotropic plate properties locate
    coincidence, and loss factor controls the smoothed dip depth through
    ``10 log10(1/eta)`` (limited to 3-30 dB).  No finite-size modes, mounting,
    joints, leaks, orthotropy, or flanking paths are represented.
    """

    mass = _positive(mass_per_area_kgm2, "mass_per_area_kgm2")
    thickness = _positive(thickness_m, "thickness_m")
    frequencies = _frequency_grid(frequencies_hz)
    properties, fallback_used = _single_panel_properties(
        material_type,
        density_kgm3,
        young_modulus_pa,
        poisson_ratio,
        loss_factor,
    )
    critical = plate_critical_frequency(
        thickness,
        properties["density_kgm3"],
        properties["young_modulus_pa"],
        properties["poisson_ratio"],
    )
    notch_depth = min(
        30.0,
        max(3.0, 10.0 * math.log10(1.0 / properties["loss_factor"])),
    )
    notch_width = 0.45 + min(0.15, 2.0 * properties["loss_factor"])

    tl: dict[str, float] = {}
    asymptote: dict[str, float] = {}
    corrections: dict[str, float] = {}
    for frequency in frequencies:
        key = _band_key(frequency)
        mass_tl = _mass_law_raw(mass, frequency)
        correction = coincidence_notch(
            frequency,
            critical,
            notch_depth,
            width_octaves=notch_width,
        )
        asymptote[key] = round(mass_tl, 1)
        corrections[key] = correction
        tl[key] = round(max(0.0, mass_tl - correction), 1)

    assumptions = [
        "engineering estimate; not a laboratory STC/Rw or certification",
        "infinite airtight homogeneous isotropic leaf with random-incidence mass law",
        "thin-plate coincidence; finite dimensions, supports, leaks, and flanking omitted",
        "coincidence dip is log-frequency smoothing controlled by representative loss factor",
    ]
    if fallback_used:
        assumptions.append("unknown material_type used concrete representative properties")

    return {
        "tl": tl,
        "mass_law_asymptote_db": asymptote,
        "coincidence_correction_db": corrections,
        "critical_frequency_hz": critical,
        "coincidence_depth_db": round(notch_depth, 1),
        "material_type": material_type,
        "material_properties": properties,
        "surface_mass_from_density_kgm2": round(
            properties["density_kgm3"] * thickness, 2
        ),
        "assumptions": assumptions,
        "is_estimate": True,
        "reference": ENGINEERING_REFERENCES["coincidence"],
    }


def single_panel_tl(
    mass_per_area_kgm2: float,
    thickness_m: float,
    material_type: str = "concreto",
    *,
    density_kgm3: float | None = None,
    young_modulus_pa: float | None = None,
    poisson_ratio: float | None = None,
    loss_factor: float | None = None,
    frequencies_hz: Iterable[float] | None = None,
) -> dict[str, float]:
    """Return the estimated single-panel TL curve (legacy six bands by default)."""

    return single_panel_tl_details(
        mass_per_area_kgm2,
        thickness_m,
        material_type,
        density_kgm3=density_kgm3,
        young_modulus_pa=young_modulus_pa,
        poisson_ratio=poisson_ratio,
        loss_factor=loss_factor,
        frequencies_hz=frequencies_hz,
    )["tl"]


def _msr_resonance_raw(
    m1: float,
    m2: float,
    gap_m: float,
    air_density_kgm3: float = AIR_DENSITY_KG_M3,
    speed_of_sound_m_s: float = SPEED_OF_SOUND_M_S,
) -> float:
    first_mass = _positive(m1, "m1")
    second_mass = _positive(m2, "m2")
    gap = _positive(gap_m, "gap_m")
    density = _positive(air_density_kgm3, "air_density_kgm3")
    speed = _positive(speed_of_sound_m_s, "speed_of_sound_m_s")
    return speed / (2.0 * math.pi) * math.sqrt(
        density * (first_mass + second_mass) / (first_mass * second_mass * gap)
    )


def msr_resonance(m1: float, m2: float, gap_m: float) -> float:
    """Return the limp-leaf mass-air-mass resonance frequency in Hz."""

    return round(_msr_resonance_raw(m1, m2, gap_m), 1)


def double_panel_tl_details(
    m1: float,
    m2: float,
    gap_m: float,
    stud_connection: bool = True,
    *,
    cavity_absorption: float = 0.0,
    bridge_penalty_db: float | None = None,
    frequencies_hz: Iterable[float] | None = None,
) -> dict:
    """Return a transparent, simplified double-leaf engineering estimate.

    Below mass-air-mass resonance the two leaves move together and the model
    uses mass law for ``m1 + m2``.  Around resonance it applies a finite 12 dB
    dip.  Above resonance it transitions to both individual leaf asymptotes
    plus a cavity-decoupling term.  ``cavity_absorption`` (0-1) can recover up
    to 6 dB near resonance and adds up to 4 dB above it.  A stud or explicit
    bridge penalty is subtracted last.

    This compact model cannot predict stud type/spacing, cavity modes, panel
    coincidence, finite dimensions, workmanship, or flanking transmission.
    Use tested assembly data for specifications.
    """

    first_mass = _positive(m1, "m1")
    second_mass = _positive(m2, "m2")
    gap = _positive(gap_m, "gap_m")
    absorption = _fraction(cavity_absorption, "cavity_absorption")
    frequencies = _frequency_grid(frequencies_hz)
    f0 = _msr_resonance_raw(first_mass, second_mass, gap)

    if bridge_penalty_db is None:
        bridge_penalty = 5.0 if stud_connection else 0.0
    else:
        bridge_penalty = _as_finite(bridge_penalty_db, "bridge_penalty_db")
        if bridge_penalty < 0:
            raise ValueError("bridge_penalty_db must be non-negative")

    tl: dict[str, float] = {}
    combined_leaf_tl: dict[str, float] = {}
    independent_leaf_tl: dict[str, float] = {}
    resonance_penalty: dict[str, float] = {}
    absorption_gain: dict[str, float] = {}
    regimes: dict[str, str] = {}

    for frequency in frequencies:
        key = _band_key(frequency)
        ratio = frequency / f0
        combined = _mass_law_raw(first_mass + second_mass, frequency)
        leaf_sum = (
            _mass_law_raw(first_mass, frequency)
            + _mass_law_raw(second_mass, frequency)
        )
        cavity_decoupling = 10.0 * math.log10(
            1.0 + (2.0 * math.pi * frequency * gap / C) ** 2
        )
        independent = max(combined, leaf_sum + cavity_decoupling)

        if ratio <= 1.0:
            transition = 0.0
            regime = "below_resonance_combined_mass"
        else:
            transition = 1.0 - math.exp(-2.5 * math.log(ratio))
            transition = min(1.0, max(0.0, transition))
            regime = "above_resonance_decoupled_leaves"

        resonance_shape = math.exp(
            -0.5 * (math.log(ratio) / math.log(1.5)) ** 2
        )
        dip = 12.0 * resonance_shape
        cavity_gain = absorption * (6.0 * resonance_shape + 4.0 * transition)
        base = combined + transition * (independent - combined)
        value = max(0.0, base - dip + cavity_gain - bridge_penalty)

        tl[key] = round(value, 1)
        combined_leaf_tl[key] = round(combined, 1)
        independent_leaf_tl[key] = round(independent, 1)
        resonance_penalty[key] = round(dip, 1)
        absorption_gain[key] = round(cavity_gain, 1)
        regimes[key] = regime

    return {
        "tl": tl,
        "mass_air_mass_resonance_hz": round(f0, 1),
        "combined_mass_asymptote_db": combined_leaf_tl,
        "independent_leaves_asymptote_db": independent_leaf_tl,
        "resonance_penalty_db": resonance_penalty,
        "cavity_absorption_gain_db": absorption_gain,
        "bridge_penalty_db": round(bridge_penalty, 1),
        "regime_by_band": regimes,
        "assumptions": [
            "engineering estimate; not a tested assembly rating or certification",
            "below resonance both leaves move together as their combined surface mass",
            "above resonance both leaf mass laws and cavity decoupling are blended",
            "cavity absorption and structural bridge effects are simplified scalar inputs",
            "panel coincidence, cavity modes, dimensions, leaks, and flanking are omitted",
        ],
        "is_estimate": True,
        "reference": ENGINEERING_REFERENCES["mass_air_mass"],
    }


def double_panel_tl(
    m1: float,
    m2: float,
    gap_m: float,
    stud_connection: bool = True,
    *,
    cavity_absorption: float = 0.0,
    bridge_penalty_db: float | None = None,
    frequencies_hz: Iterable[float] | None = None,
) -> dict[str, float]:
    """Return double-panel TL (legacy six octave bands by default)."""

    return double_panel_tl_details(
        m1,
        m2,
        gap_m,
        stud_connection,
        cavity_absorption=cavity_absorption,
        bridge_penalty_db=bridge_penalty_db,
        frequencies_hz=frequencies_hz,
    )["tl"]


# ASTM E413 contour offsets relative to the contour value at 500 Hz (the STC).
STC_REFERENCE_OFFSETS: dict[int, int] = {
    125: -16,
    160: -13,
    200: -10,
    250: -7,
    315: -4,
    400: -1,
    500: 0,
    630: 1,
    800: 2,
    1000: 3,
    1250: 4,
    1600: 4,
    2000: 4,
    2500: 4,
    3150: 4,
    4000: 4,
}
STC_REFERENCE: list[tuple[int, int]] = list(STC_REFERENCE_OFFSETS.items())

# ISO 717-1 public reference curve and offsets relative to its 500 Hz value.
ISO717_REFERENCE_VALUES: dict[int, int] = {
    100: 33,
    125: 36,
    160: 39,
    200: 42,
    250: 45,
    315: 48,
    400: 51,
    500: 52,
    630: 53,
    800: 54,
    1000: 55,
    1250: 56,
    1600: 56,
    2000: 56,
    2500: 56,
    3150: 56,
}
RW_REFERENCE_OFFSETS: dict[int, int] = {
    frequency: value - ISO717_REFERENCE_VALUES[500]
    for frequency, value in ISO717_REFERENCE_VALUES.items()
}
RW_REFERENCE: list[tuple[int, int]] = list(ISO717_REFERENCE_VALUES.items())

# ISO 717-1 standardized, A-weighted source spectra over 100-3150 Hz.
ISO717_SPECTRUM_C: dict[int, int] = dict(zip(
    ISO717_BANDS_HZ,
    (-29, -26, -23, -21, -19, -17, -15, -13,
     -12, -11, -10, -9, -9, -9, -9, -9),
))
ISO717_SPECTRUM_CTR: dict[int, int] = dict(zip(
    ISO717_BANDS_HZ,
    (-20, -20, -18, -16, -15, -14, -13, -12,
     -11, -9, -8, -9, -10, -11, -13, -15),
))


def _match_frequency(frequency: float, required: Sequence[float]) -> float | None:
    nearest = min(required, key=lambda candidate: abs(float(candidate) - frequency))
    tolerance = max(0.01, abs(float(nearest)) * 0.01)
    return float(nearest) if abs(float(nearest) - frequency) <= tolerance else None


def _parse_curve(curve: Mapping[str | int | float, float]) -> dict[float, float]:
    if not isinstance(curve, Mapping) or not curve:
        raise ValueError("curve must be a non-empty frequency-to-level mapping")
    parsed: dict[float, float] = {}
    for raw_frequency, raw_value in curve.items():
        frequency = _positive(raw_frequency, "curve frequency")
        if frequency in parsed:
            raise ValueError(f"duplicate curve frequency: {frequency:g} Hz")
        parsed[frequency] = _as_finite(raw_value, f"curve value at {frequency:g} Hz")
    return parsed


def _log_frequency_interpolate(source: Mapping[float, float], frequency: float) -> float:
    points = sorted(source.items())
    if frequency in source:
        return source[frequency]
    if frequency < points[0][0]:
        lower, upper = points[0], points[1]
    elif frequency > points[-1][0]:
        lower, upper = points[-2], points[-1]
    else:
        lower, upper = points[0], points[-1]
        for left, right in zip(points, points[1:]):
            if left[0] <= frequency <= right[0]:
                lower, upper = left, right
                break
    fraction = math.log(frequency / lower[0]) / math.log(upper[0] / lower[0])
    return lower[1] + fraction * (upper[1] - lower[1])


def _required_curve(
    curve: Mapping[str | int | float, float],
    required: Sequence[float],
    *,
    allow_legacy_octaves: bool = True,
) -> tuple[dict[float, float], bool]:
    parsed = _parse_curve(curve)
    selected: dict[float, float] = {}
    for frequency, value in parsed.items():
        matched = _match_frequency(frequency, required)
        if matched is not None:
            if matched in selected:
                raise ValueError(f"duplicate standard band near {matched:g} Hz")
            selected[matched] = value

    required_floats = tuple(float(frequency) for frequency in required)
    if all(frequency in selected for frequency in required_floats):
        return {frequency: selected[frequency] for frequency in required_floats}, False

    legacy: dict[float, float] = {}
    for frequency, value in parsed.items():
        matched = _match_frequency(frequency, OCTAVE_BANDS_HZ)
        if matched is not None:
            legacy[matched] = value
    if allow_legacy_octaves and set(legacy) == {float(f) for f in OCTAVE_BANDS_HZ}:
        return {
            frequency: _log_frequency_interpolate(legacy, frequency)
            for frequency in required_floats
        }, True

    missing = [
        _band_key(frequency)
        for frequency in required_floats
        if frequency not in selected
    ]
    raise ValueError(f"missing required bands: {', '.join(missing)} Hz")


def _contour_diagnostics(
    values: Mapping[int, float],
    offsets: Mapping[int, int],
    rating: int,
) -> tuple[dict[str, int], dict[str, float], float, float]:
    contour = {str(frequency): rating + offset for frequency, offset in offsets.items()}
    deficiency_by_band = {
        str(frequency): max(0.0, contour[str(frequency)] - values[frequency])
        for frequency in offsets
    }
    total = sum(deficiency_by_band.values())
    maximum = max(deficiency_by_band.values(), default=0.0)
    return contour, deficiency_by_band, total, maximum


def calculate_stc(tl_curve: Mapping[str | int | float, float]) -> dict:
    """Fit the ASTM E413 STC contour to all 16 required one-third bands.

    Values are rounded to whole decibels (half up) before fitting.  The highest
    integer contour satisfying total deficiency <= 32 dB and every individual
    deficiency <= 8 dB is selected.  Complete-band calculation is a
    classification operation, not proof that the input was measured to E90.
    """

    prepared, interpolated = _required_curve(tl_curve, STC_BANDS_HZ)
    values = {
        int(frequency): float(_round_half_up(value))
        for frequency, value in prepared.items()
    }
    no_deficiency_rating = min(
        values[frequency] - STC_REFERENCE_OFFSETS[frequency]
        for frequency in STC_BANDS_HZ
    )
    upper_rating = math.floor(no_deficiency_rating) + 8

    rating = math.floor(no_deficiency_rating)
    for trial in range(upper_rating, math.floor(no_deficiency_rating) - 1, -1):
        _, _, total, maximum = _contour_diagnostics(
            values, STC_REFERENCE_OFFSETS, trial
        )
        if total <= 32.0 + 1e-9 and maximum <= 8.0 + 1e-9:
            rating = trial
            break

    contour, deficiencies, total, maximum = _contour_diagnostics(
        values, STC_REFERENCE_OFFSETS, rating
    )
    deficiency_by_band = {
        band: round(value, 1) for band, value in deficiencies.items()
    }
    governing = [
        band for band, value in deficiency_by_band.items()
        if value == round(maximum, 1) and value > 0
    ]
    return {
        "stc": rating,
        "shift": rating,
        "contour_shift_db": rating,
        "deficiencies": round(total, 1),
        "total_deficiency_db": round(total, 1),
        "max_deficiency_db": round(maximum, 1),
        "deficiency_by_band_db": deficiency_by_band,
        "contour_db": contour,
        "tl_used_db": {str(frequency): values[frequency] for frequency in STC_BANDS_HZ},
        "governing_bands_hz": governing,
        "input_complete": not interpolated,
        "is_estimate": interpolated,
        "input_basis": (
            "legacy octave curve log-frequency interpolation; engineering estimate"
            if interpolated
            else "16 supplied ASTM E413 bands"
        ),
        "method": "ASTM E413-22 public contour algorithm",
        "not_certification": True,
        "reference": ENGINEERING_REFERENCES["astm_e413"],
    }


def _spectrum_adaptation(
    values: Mapping[int, float],
    spectrum: Mapping[int, int],
    weighted_rating: int,
) -> tuple[int, float]:
    level_terms = [
        spectrum[frequency] - values[frequency]
        for frequency in ISO717_BANDS_HZ
    ]
    maximum_term = max(level_terms)
    logarithmic_sum = maximum_term + 10.0 * math.log10(sum(
        10.0 ** ((term - maximum_term) / 10.0) for term in level_terms
    ))
    adapted_level = -logarithmic_sum
    term = int(_round_half_up(adapted_level - weighted_rating))
    return term, adapted_level


def calculate_rw(tl_curve: Mapping[str | int | float, float]) -> dict:
    """Fit ISO 717-1 Rw and calculate the C and Ctr adaptation terms.

    The reference curve is shifted in 1 dB steps over 100-3150 Hz.  The sum of
    unfavorable deviations may not exceed 32 dB; unlike STC, ISO 717-1 has no
    8 dB individual-band constraint.  C and Ctr use the public standardized
    spectra and energetic summation.
    """

    prepared, interpolated = _required_curve(tl_curve, ISO717_BANDS_HZ)
    values = {int(frequency): value for frequency, value in prepared.items()}
    no_deficiency_rating = min(
        values[frequency] - RW_REFERENCE_OFFSETS[frequency]
        for frequency in ISO717_BANDS_HZ
    )
    upper_rating = math.floor(no_deficiency_rating) + 32

    rating = math.floor(no_deficiency_rating)
    for trial in range(upper_rating, math.floor(no_deficiency_rating) - 1, -1):
        _, _, total, _ = _contour_diagnostics(values, RW_REFERENCE_OFFSETS, trial)
        if total <= 32.0 + 1e-9:
            rating = trial
            break

    contour, deficiencies, total, maximum = _contour_diagnostics(
        values, RW_REFERENCE_OFFSETS, rating
    )
    c_term, c_level = _spectrum_adaptation(values, ISO717_SPECTRUM_C, rating)
    ctr_term, ctr_level = _spectrum_adaptation(values, ISO717_SPECTRUM_CTR, rating)
    deficiency_by_band = {
        band: round(value, 1) for band, value in deficiencies.items()
    }
    governing = [
        band for band, value in deficiency_by_band.items()
        if value == round(maximum, 1) and value > 0
    ]
    return {
        "rw": rating,
        "shift": rating,
        "contour_shift_db": rating - ISO717_REFERENCE_VALUES[500],
        "c": c_term,
        "ctr": ctr_term,
        "rw_c": rating + c_term,
        "rw_ctr": rating + ctr_term,
        "spectrum_adapted_level_c_db": round(c_level, 1),
        "spectrum_adapted_level_ctr_db": round(ctr_level, 1),
        "deficiencies": round(total, 1),
        "total_deficiency_db": round(total, 1),
        "max_deficiency_db": round(maximum, 1),
        "deficiency_by_band_db": deficiency_by_band,
        "contour_db": contour,
        "tl_used_db": {
            str(frequency): round(values[frequency], 1)
            for frequency in ISO717_BANDS_HZ
        },
        "governing_bands_hz": governing,
        "input_complete": not interpolated,
        "is_estimate": interpolated,
        "input_basis": (
            "legacy octave curve log-frequency interpolation/extrapolation; engineering estimate"
            if interpolated
            else "16 supplied ISO 717-1 bands"
        ),
        "method": "ISO 717-1:2020 public contour and spectrum-adaptation algorithm",
        "not_certification": True,
        "reference": ENGINEERING_REFERENCES["iso_717"],
    }


NC_FREQS = (63, 125, 250, 500, 1000, 2000, 4000, 8000)
NC_CURVES: dict[int, list[float]] = {
    15: [47, 36, 29, 22, 17, 14, 12, 11],
    20: [51, 40, 33, 26, 22, 19, 17, 16],
    25: [54, 44, 37, 31, 27, 24, 22, 21],
    30: [57, 48, 41, 35, 31, 29, 28, 27],
    35: [60, 52, 45, 40, 36, 34, 33, 32],
    40: [64, 56, 50, 45, 41, 39, 38, 37],
    45: [67, 60, 54, 49, 46, 44, 43, 42],
    50: [71, 64, 58, 54, 51, 49, 48, 47],
    55: [74, 67, 62, 58, 56, 54, 53, 52],
    60: [77, 71, 67, 63, 61, 59, 58, 57],
    65: [80, 75, 71, 68, 66, 64, 63, 62],
    70: [83, 79, 75, 72, 71, 70, 69, 68],
}

NR_FREQS = (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000)
NR_CURVES: dict[int, list[float]] = {
    0: [55, 36, 22, 12, 5, 0, -4, -6, -8],
    10: [62, 43, 31, 21, 15, 10, 7, 4, 2],
    20: [69, 51, 39, 31, 24, 20, 17, 14, 13],
    30: [76, 59, 48, 40, 34, 30, 27, 25, 23],
    40: [83, 67, 57, 49, 44, 40, 37, 35, 33],
    50: [89, 75, 66, 59, 54, 50, 47, 45, 44],
    60: [96, 83, 74, 68, 63, 60, 57, 55, 54],
    70: [103, 91, 83, 77, 73, 70, 68, 66, 64],
    80: [110, 99, 92, 86, 83, 80, 78, 76, 74],
    90: [117, 107, 100, 96, 93, 90, 88, 86, 85],
    100: [124, 115, 109, 105, 102, 100, 98, 96, 95],
    110: [130, 122, 118, 114, 112, 110, 108, 107, 105],
    120: [137, 130, 126, 124, 122, 120, 118, 117, 116],
    130: [144, 138, 135, 133, 131, 130, 128, 127, 126],
}


def _evaluate_tabulated_noise_curve(
    spl_curve: Mapping[str | int | float, float],
    frequencies: Sequence[float],
    curves: Mapping[int, Sequence[float]],
    prefix: str,
) -> dict:
    prepared, interpolated = _required_curve(spl_curve, frequencies)
    levels = {float(frequency): prepared[float(frequency)] for frequency in frequencies}
    curve_numbers = sorted(curves)

    per_band: dict[str, int | None] = {}
    for index, frequency in enumerate(frequencies):
        per_band[_band_key(float(frequency))] = next(
            (
                curve_number
                for curve_number in curve_numbers
                if levels[float(frequency)] <= curves[curve_number][index] + 1e-9
            ),
            None,
        )

    selected = next(
        (
            curve_number
            for curve_number in curve_numbers
            if all(
                levels[float(frequency)] <= curves[curve_number][index] + 1e-9
                for index, frequency in enumerate(frequencies)
            )
        ),
        None,
    )
    above_range = selected is None
    if selected is None:
        margins = {
            _band_key(float(frequency)): round(
                curves[curve_numbers[-1]][index] - levels[float(frequency)], 1
            )
            for index, frequency in enumerate(frequencies)
        }
        classification = f">{prefix}-{curve_numbers[-1]}"
        governing = [band for band, margin in margins.items() if margin < 0]
    else:
        margins = {
            _band_key(float(frequency)): round(
                curves[selected][index] - levels[float(frequency)], 1
            )
            for index, frequency in enumerate(frequencies)
        }
        classification = f"{prefix}-{selected}"
        minimum_margin = min(margins.values())
        governing = [band for band, margin in margins.items() if margin == minimum_margin]

    return {
        prefix.lower(): selected,
        "classification": classification,
        f"{prefix.lower()}_by_band": per_band,
        "margin_by_band_db": margins,
        "governing_bands_hz": governing,
        "above_tabulated_range": above_range,
        "below_lowest_tabulated_curve": (
            selected == curve_numbers[0]
            and all(
                levels[float(frequency)] < curves[curve_numbers[0]][index]
                for index, frequency in enumerate(frequencies)
            )
        ),
        "input_complete": not interpolated,
        "is_estimate": interpolated,
        "input_basis": (
            "legacy octave curve log-frequency interpolation/extrapolation; engineering estimate"
            if interpolated
            else f"full {prefix} octave-band set"
        ),
        "method": f"lowest enveloping public tabulated {prefix} curve",
        "not_certification": True,
    }


def evaluate_nc(spl_curve: Mapping[str | int | float, float]) -> dict:
    """Classify all 63-8000 Hz bands against explicit public NC tables."""

    result = _evaluate_tabulated_noise_curve(spl_curve, NC_FREQS, NC_CURVES, "NC")
    result["reference"] = ENGINEERING_REFERENCES["nc"]
    return result


def evaluate_nr(spl_curve: Mapping[str | int | float, float]) -> dict:
    """Classify all 31.5-8000 Hz bands against explicit public NR tables."""

    result = _evaluate_tabulated_noise_curve(spl_curve, NR_FREQS, NR_CURVES, "NR")
    result["reference"] = ENGINEERING_REFERENCES["nr"]
    return result


NC_TARGETS: dict[str, dict] = {
    "estudio_grabacion": {
        "label": "Estudio de grabación", "nc": 15, "nc_max": 20,
        "basis": "public recommended NC range; project target, not certification",
    },
    "sala_conciertos": {
        "label": "Sala de conciertos", "nc": 15, "nc_max": 20,
        "basis": "public recommended NC range; project target, not certification",
    },
    "teatro": {
        "label": "Teatro", "nc": 20, "nc_max": 25,
        "basis": "public recommended NC range; project target, not certification",
    },
    "oficina_ejecutiva": {
        "label": "Oficina ejecutiva", "nc": 30, "nc_max": 35,
        "basis": "public private-office NC range; project target, not certification",
    },
    "aula": {
        "label": "Aula", "nc": 25, "nc_max": 30,
        "basis": "public classroom NC range; project target, not certification",
    },
    "restaurante": {
        "label": "Restaurante", "nc": 40, "nc_max": 45,
        "basis": "public restaurant NC range; project target, not certification",
    },
}

NR_TARGETS: dict[str, dict] = {
    "estudio_grabacion": {"label": "Estudio de grabación", "nr_max": 25},
    "sala_conciertos": {"label": "Sala de conciertos", "nr_max": 25},
    "teatro": {"label": "Teatro", "nr_max": 30},
    "oficina_ejecutiva": {"label": "Oficina ejecutiva", "nr_max": 35},
    "aula": {"label": "Aula", "nr_max": 35},
    "restaurante": {"label": "Restaurante", "nr_max": 40},
}

# These isolation values are deliberately planning estimates, not code claims.
ISOLATION_TARGETS: dict[str, dict] = {
    "estudio_grabacion": {"stc_min": 60, "rw_min": 60},
    "sala_conciertos": {"stc_min": 55, "rw_min": 55},
    "teatro": {"stc_min": 55, "rw_min": 55},
    "oficina_ejecutiva": {"stc_min": 45, "rw_min": 45},
    "aula": {"stc_min": 50, "rw_min": 50},
    "restaurante": {"stc_min": 50, "rw_min": 50},
}


# The frontend uses the same use-codes as ``acoustic_core/design.py``; some do
# not exist verbatim in the isolation target tables, so map them to the nearest
# planning target key.
USE_ALIASES: dict[str, str] = {
    "home_studio": "estudio_grabacion",
    "home_theater": "teatro",
    "sala_conferencias": "oficina_ejecutiva",
    "iglesia": "sala_conciertos",
}


def resolve_target_use(uso: str) -> str:
    return USE_ALIASES.get(uso, uso)


def get_nc_target(uso: str) -> dict | None:
    return NC_TARGETS.get(resolve_target_use(uso))


def get_nr_target(uso: str) -> dict | None:
    target = NR_TARGETS.get(resolve_target_use(uso))
    if target is None:
        return None
    return {
        **target,
        "basis": "public recommended NR application; project target, not certification",
    }


def compare_target_by_use(
    uso: str,
    *,
    nc: float | None = None,
    nr: float | None = None,
    stc: float | None = None,
    rw: float | None = None,
) -> dict:
    """Compare supplied metrics with labelled planning targets for ``uso``."""

    uso = resolve_target_use(uso)
    if uso not in NC_TARGETS:
        raise ValueError(f"unknown use: {uso}")
    supplied = {"nc": nc, "nr": nr, "stc": stc, "rw": rw}
    if all(value is None for value in supplied.values()):
        raise ValueError("at least one of nc, nr, stc, or rw must be supplied")

    targets = {
        "nc": NC_TARGETS[uso]["nc_max"],
        "nr": NR_TARGETS[uso]["nr_max"],
        "stc": ISOLATION_TARGETS[uso]["stc_min"],
        "rw": ISOLATION_TARGETS[uso]["rw_min"],
    }
    comparisons: dict[str, dict] = {}
    for metric, raw_value in supplied.items():
        if raw_value is None:
            continue
        value = _as_finite(raw_value, metric)
        target = targets[metric]
        lower_is_better = metric in {"nc", "nr"}
        meets = value <= target if lower_is_better else value >= target
        margin = target - value if lower_is_better else value - target
        comparisons[metric] = {
            "value": value,
            "target_max" if lower_is_better else "target_min": target,
            "margin_db": round(margin, 1),
            "meets_target": meets,
        }

    return {
        "uso": uso,
        "label": NC_TARGETS[uso]["label"],
        "comparisons": comparisons,
        "meets_all_targets": all(item["meets_target"] for item in comparisons.values()),
        "basis": (
            "NC/NR ranges are public recommendations; STC/Rw values are planning "
            "estimates. Verify jurisdiction, source spectrum, and project brief."
        ),
        "not_certification": True,
    }


def compare_nc_target(uso: str, nc: float) -> dict:
    return compare_target_by_use(uso, nc=nc)


def compare_nr_target(uso: str, nr: float) -> dict:
    return compare_target_by_use(uso, nr=nr)


def compare_isolation_target(
    uso: str,
    *,
    stc: float | None = None,
    rw: float | None = None,
) -> dict:
    if stc is None and rw is None:
        raise ValueError("stc or rw must be supplied")
    return compare_target_by_use(uso, stc=stc, rw=rw)


def rectangular_lined_duct_attenuation(
    width_m: float,
    height_m: float,
    length_m: float,
    absorption_coefficients: float | Mapping[str | int | float, float],
    *,
    lined_perimeter_fraction: float = 1.0,
    frequencies_hz: Iterable[float] | None = None,
) -> dict:
    """Estimate octave-band insertion loss of a straight rectangular lined duct.

    The Sabine empirical relation is ``IL = 1.05 alpha^1.4 (P_lined/A) L``.
    Frequency dependence comes from the supplied absorption coefficients.  It
    excludes airflow self-noise, pressure loss, breakout, end reflections,
    bends, higher modes, lining thickness/facing effects, and installation
    tolerances.  Manufacturer insertion-loss data should be used for design.
    """

    width = _positive(width_m, "width_m")
    height = _positive(height_m, "height_m")
    length = _positive(length_m, "length_m")
    lined_fraction = _fraction(lined_perimeter_fraction, "lined_perimeter_fraction")
    frequencies = _frequency_grid(frequencies_hz)

    if isinstance(absorption_coefficients, Mapping):
        prepared, interpolated = _required_curve(
            absorption_coefficients,
            frequencies,
            allow_legacy_octaves=False,
        )
        if interpolated:  # Defensive; disabled above.
            raise ValueError("absorption coefficients must cover every requested frequency")
        coefficients = {
            frequency: _fraction(prepared[frequency], f"absorption at {frequency:g} Hz")
            for frequency in frequencies
        }
    else:
        coefficient = _fraction(absorption_coefficients, "absorption_coefficients")
        coefficients = {frequency: coefficient for frequency in frequencies}

    area = width * height
    full_perimeter = 2.0 * (width + height)
    lined_perimeter = full_perimeter * lined_fraction
    perimeter_area_ratio = lined_perimeter / area
    attenuation_per_m = {
        _band_key(frequency): round(
            1.05 * coefficients[frequency] ** 1.4 * perimeter_area_ratio,
            2,
        )
        for frequency in frequencies
    }
    insertion_loss = {
        band: round(value * length, 1)
        for band, value in attenuation_per_m.items()
    }
    return {
        "insertion_loss_db": insertion_loss,
        "attenuation_db_per_m": attenuation_per_m,
        "absorption_coefficients": {
            _band_key(frequency): coefficients[frequency] for frequency in frequencies
        },
        "cross_section_area_m2": round(area, 4),
        "lined_perimeter_m": round(lined_perimeter, 4),
        "perimeter_area_ratio_m_inv": round(perimeter_area_ratio, 4),
        "method": "simplified Sabine rectangular lined-duct engineering estimate",
        "assumptions": [
            "straight uniform duct with no flow and all specified perimeter uniformly lined",
            "absorption coefficient represents installed lining at each frequency",
            "breakout, regenerated noise, pressure loss, bends, transitions, and reflections omitted",
        ],
        "is_estimate": True,
        "not_certification": True,
        "reference": ENGINEERING_REFERENCES["lined_duct"],
    }


def lined_duct_attenuation(*args, **kwargs) -> dict:
    """Alias for :func:`rectangular_lined_duct_attenuation`."""

    return rectangular_lined_duct_attenuation(*args, **kwargs)


def energetic_flanking_sum(path_tl_db: Sequence[float]) -> float:
    """Aggregate parallel path TL values by transmission energy.

    Equal normalized areas are assumed.  Two 50 dB paths therefore produce
    46.99 dB apparent TL.  This is only the energetic final step, not an ISO
    12354 prediction of the individual paths.
    """

    if isinstance(path_tl_db, (str, bytes)) or not path_tl_db:
        raise ValueError("path_tl_db must contain at least one path")
    values = [_as_finite(value, "path_tl_db") for value in path_tl_db]
    minimum = min(values)
    relative_transmission = sum(10.0 ** (-(value - minimum) / 10.0) for value in values)
    return round(minimum - 10.0 * math.log10(relative_transmission), 2)


def aggregate_flanking_paths(
    direct_tl_db: float | Mapping[str | int | float, float],
    flanking_paths_tl_db: Sequence[float] | Sequence[Mapping[str | int | float, float]],
) -> dict:
    """Return a simplified apparent TL from direct and flanking paths.

    The helper is inspired by ISO 12354's energetic path aggregation but is
    explicitly not an ISO 12354 model: path areas, junction vibration indices,
    structural reverberation, coupling lengths, and radiation efficiencies are
    not calculated.  Inputs must already be equivalent normalized path TLs.
    """

    if isinstance(flanking_paths_tl_db, (str, bytes)) or not flanking_paths_tl_db:
        raise ValueError("flanking_paths_tl_db must contain at least one path")

    if isinstance(direct_tl_db, Mapping):
        direct = _parse_curve(direct_tl_db)
        curves: list[dict[float, float]] = []
        for path in flanking_paths_tl_db:
            if not isinstance(path, Mapping):
                raise ValueError("all flanking paths must be curves when direct_tl_db is a curve")
            parsed = _parse_curve(path)
            if set(parsed) != set(direct):
                raise ValueError("all path curves must have identical frequency bands")
            curves.append(parsed)
        apparent = {
            _band_key(frequency): energetic_flanking_sum(
                [direct[frequency], *(curve[frequency] for curve in curves)]
            )
            for frequency in sorted(direct)
        }
    else:
        if any(isinstance(path, Mapping) for path in flanking_paths_tl_db):
            raise ValueError("flanking path types must match direct_tl_db")
        apparent = energetic_flanking_sum([
            _as_finite(direct_tl_db, "direct_tl_db"),
            *(_as_finite(path, "flanking path TL") for path in flanking_paths_tl_db),
        ])

    return {
        "apparent_tl_db": apparent,
        "path_count": 1 + len(flanking_paths_tl_db),
        "method": "simplified equal-normalization energetic path aggregation estimate",
        "assumptions": [
            "inputs are already equivalent path transmission losses on the same normalization",
            "paths are incoherent and their transmission coefficients add",
            "no ISO 12354 junction, geometry, area, or structural corrections are calculated",
        ],
        "is_estimate": True,
        "not_iso_12354_prediction": True,
        "reference": ENGINEERING_REFERENCES["iso_12354_scope"],
    }


def estimate_flanking_aggregation(*args, **kwargs) -> dict:
    """Explicitly named alias for :func:`aggregate_flanking_paths`."""

    return aggregate_flanking_paths(*args, **kwargs)

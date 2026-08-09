"""Engineering estimates for common acoustic absorber constructions.

The models are useful for screening and parameter studies.  They are not
substitutes for impedance-tube/reverberation-room measurements or product
certification, and every detailed result says so explicitly.
"""

from __future__ import annotations

from collections.abc import Mapping
import cmath
import math
import warnings

from .models import BANDAS_OCTAVA


C = 343.0
RHO = 1.2
Z0 = C * RHO
ESTIMATE_LABEL = "engineering_estimate_not_measurement_or_certification"
DEPRECATED_DENSITY_NOTE = (
    "density_kgm3 is retained for API compatibility but is ignored: the "
    "Delany-Bazley model is parameterized by airflow resistivity and ambient "
    "air properties, not porous bulk density."
)


def _zero_curve() -> dict[str, float]:
    return {band: 0.0 for band in BANDAS_OCTAVA}


def _finite(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _positive(value: float, name: str, *, allow_zero: bool = False) -> float:
    converted = _finite(value, name)
    if converted < 0.0 if allow_zero else converted <= 0.0:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ValueError(f"{name} must be {qualifier}")
    return converted


def _bounded(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return min(1.0, max(0.0, value))


def _porous_surface_impedance(
    frequency_hz: float,
    thickness_m: float,
    flow_resistivity: float,
    air_gap_m: float,
    sound_speed_m_s: float,
    air_density_kgm3: float,
) -> tuple[complex, float]:
    """Return rigid-backed layer impedance and the Delany-Bazley X value."""

    x_value = air_density_kgm3 * frequency_hz / flow_resistivity
    z_air = sound_speed_m_s * air_density_kgm3
    z_characteristic = z_air * (
        1.0
        + 0.0571 * x_value**-0.754
        - 1j * 0.0870 * x_value**-0.732
    )
    k_air = 2.0 * math.pi * frequency_hz / sound_speed_m_s
    k_porous = k_air * (
        1.0
        + 0.0978 * x_value**-0.700
        - 1j * 0.1890 * x_value**-0.595
    )

    if air_gap_m == 0.0:
        surface_impedance = -1j * z_characteristic / cmath.tan(
            k_porous * thickness_m
        )
        return surface_impedance, x_value

    air_tangent = math.tan(k_air * air_gap_m)
    if abs(air_tangent) < 1e-12:
        air_tangent = math.copysign(1e-12, air_tangent or 1.0)
    gap_impedance = -1j * z_air / air_tangent
    cosine = cmath.cos(k_porous * thickness_m)
    sine = cmath.sin(k_porous * thickness_m)
    numerator = gap_impedance * cosine + 1j * z_characteristic * sine
    denominator = z_characteristic * cosine + 1j * gap_impedance * sine
    return z_characteristic * numerator / denominator, x_value


def porous_absorber_estimate(
    thickness_m: float,
    flow_resistivity: float,
    density_kgm3: float | None = 100.0,
    *,
    air_gap_m: float = 0.0,
    incidence_angle_deg: float = 0.0,
    strict_validity: bool = False,
    sound_speed_m_s: float = C,
    air_density_kgm3: float = RHO,
) -> dict:
    """Estimate a porous layer using the empirical Delany-Bazley model.

    The published empirical range is reported band-by-band as
    ``0.01 <= rho_air*f/sigma <= 1``.  Oblique incidence is a locally-reacting
    boundary estimate, and the optional air gap is an ideal lossless cavity.
    """

    thickness = _positive(thickness_m, "thickness_m")
    resistivity = _positive(flow_resistivity, "flow_resistivity")
    gap = _positive(air_gap_m, "air_gap_m", allow_zero=True)
    angle = _finite(incidence_angle_deg, "incidence_angle_deg")
    if not 0.0 <= angle < 90.0:
        raise ValueError("incidence_angle_deg must be in [0, 90)")
    sound_speed = _positive(sound_speed_m_s, "sound_speed_m_s")
    air_density = _positive(air_density_kgm3, "air_density_kgm3")

    density_input = None
    if density_kgm3 is not None:
        density_input = _positive(density_kgm3, "density_kgm3")
        warnings.warn(DEPRECATED_DENSITY_NOTE, DeprecationWarning, stacklevel=2)

    alpha: dict[str, float] = {}
    validity_parameter: dict[str, float] = {}
    valid_by_band: dict[str, bool] = {}
    cosine = math.cos(math.radians(angle))
    z_air = sound_speed * air_density
    for band in BANDAS_OCTAVA:
        frequency = float(band)
        surface_impedance, x_value = _porous_surface_impedance(
            frequency,
            thickness,
            resistivity,
            gap,
            sound_speed,
            air_density,
        )
        reflection = (surface_impedance * cosine - z_air) / (
            surface_impedance * cosine + z_air
        )
        alpha[band] = round(_bounded(1.0 - abs(reflection) ** 2), 4)
        validity_parameter[band] = round(x_value, 6)
        valid_by_band[band] = 0.01 <= x_value <= 1.0

    outside = [band for band, valid in valid_by_band.items() if not valid]
    if strict_validity and outside:
        raise ValueError(
            "Delany-Bazley validity range exceeded at: "
            + ", ".join(f"{band} Hz" for band in outside)
        )

    effective_depth = thickness + gap
    assumptions = [
        "Delany-Bazley 1970 empirical normal-incidence equivalent-fluid model.",
        "Rigid backing and homogeneous isotropic porous material are assumed.",
        "The quarter-wave frequency is a depth heuristic, not an absorption peak prediction.",
        DEPRECATED_DENSITY_NOTE,
    ]
    if gap > 0.0:
        assumptions.append("The air gap is modeled as an ideal lossless transfer layer.")
    if angle > 0.0:
        assumptions.append(
            "Angle correction assumes a locally reacting surface impedance."
        )
    return {
        "model": "Delany-Bazley 1970",
        "alpha": alpha,
        "quarter_wave_frequency_hz": round(sound_speed / (4.0 * effective_depth), 2),
        "quarter_wave_effective_depth_m": round(effective_depth, 6),
        "air_gap_m": gap,
        "incidence_angle_deg": angle,
        "flow_resistivity_pa_s_m2": resistivity,
        "density_input_kgm3": density_input,
        "density_input_used": False,
        "validity_parameter_rho_f_over_sigma": validity_parameter,
        "valid_by_band": valid_by_band,
        "outside_validity_bands": outside,
        "valid_for_all_bands": not outside,
        "assumptions": assumptions,
        "reference": "Delany and Bazley, Applied Acoustics 3 (1970), 105-116",
        "estimate_label": ESTIMATE_LABEL,
    }


def porous_absorption(
    thickness_m: float,
    flow_resistivity: float,
    density_kgm3: float = 100.0,
    *,
    air_gap_m: float = 0.0,
    incidence_angle_deg: float = 0.0,
    strict_validity: bool = False,
) -> dict[str, float]:
    """Legacy spectrum wrapper around :func:`porous_absorber_estimate`."""

    thickness = _finite(thickness_m, "thickness_m")
    resistivity = _finite(flow_resistivity, "flow_resistivity")
    if thickness <= 0.0 or resistivity <= 0.0:
        return _zero_curve()
    return porous_absorber_estimate(
        thickness,
        resistivity,
        density_kgm3,
        air_gap_m=air_gap_m,
        incidence_angle_deg=incidence_angle_deg,
        strict_validity=strict_validity,
    )["alpha"]


def _zero_resonator(model: str, reason: str) -> dict:
    return {
        "model": model,
        "f0": 0.0,
        "Q": 0.0,
        "alpha": _zero_curve(),
        "error": reason,
        "estimate_label": ESTIMATE_LABEL,
    }


def helmholtz_resonator(
    neck_area_m2: float | None,
    cavity_volume_m3: float,
    neck_length_m: float,
    neck_radius_m: float | None = None,
    *,
    panel_area_m2: float | None = None,
    open_area_ratio: float | None = None,
    hole_count: int | None = None,
    end_correction_coefficient: float = 1.7,
    quality_factor: float | None = None,
    loss_factor: float | None = None,
    peak_absorption: float = 1.0,
    sound_speed_m_s: float = C,
) -> dict:
    """Estimate a lumped Helmholtz/perforated-panel resonator.

    ``neck_area_m2`` is total open area.  Radius is the radius of each opening;
    when no hole count is supplied, the reported effective count reconciles the
    two inputs.  Alternatively, total open area can be derived from panel area
    and perforation ratio.
    """

    try:
        cavity_volume = _positive(cavity_volume_m3, "cavity_volume_m3")
        neck_length = _positive(neck_length_m, "neck_length_m", allow_zero=True)
        sound_speed = _positive(sound_speed_m_s, "sound_speed_m_s")
    except (TypeError, ValueError) as exc:
        return _zero_resonator("lumped_helmholtz", str(exc))

    area_from_ratio = None
    if panel_area_m2 is not None or open_area_ratio is not None:
        if panel_area_m2 is None or open_area_ratio is None:
            raise ValueError("panel_area_m2 and open_area_ratio must be supplied together")
        panel_area = _positive(panel_area_m2, "panel_area_m2")
        ratio = _positive(open_area_ratio, "open_area_ratio")
        if ratio > 1.0:
            raise ValueError("open_area_ratio must not exceed 1")
        area_from_ratio = panel_area * ratio
    else:
        panel_area = None
        ratio = None

    if neck_area_m2 is None:
        total_area = area_from_ratio
    else:
        total_area = _finite(neck_area_m2, "neck_area_m2")
        if total_area <= 0.0:
            return _zero_resonator("lumped_helmholtz", "neck_area_m2 must be positive")
    if total_area is None:
        if neck_radius_m is None or hole_count is None:
            return _zero_resonator(
                "lumped_helmholtz",
                "provide neck area, panel open-area data, or radius plus hole_count",
            )
        radius_for_area = _positive(neck_radius_m, "neck_radius_m")
        if isinstance(hole_count, bool) or not isinstance(hole_count, int) or hole_count <= 0:
            raise ValueError("hole_count must be a positive integer")
        total_area = hole_count * math.pi * radius_for_area**2

    if area_from_ratio is not None and not math.isclose(
        total_area, area_from_ratio, rel_tol=0.01, abs_tol=1e-9
    ):
        raise ValueError("neck_area_m2 is inconsistent with panel open-area data")

    if hole_count is not None:
        if isinstance(hole_count, bool) or not isinstance(hole_count, int) or hole_count <= 0:
            raise ValueError("hole_count must be a positive integer")
    if neck_radius_m is None:
        count_for_radius = hole_count or 1
        radius = math.sqrt(total_area / (math.pi * count_for_radius))
    else:
        radius = _positive(neck_radius_m, "neck_radius_m")

    geometric_count = total_area / (math.pi * radius**2)
    if hole_count is not None and not math.isclose(
        geometric_count, hole_count, rel_tol=0.01, abs_tol=1e-9
    ):
        raise ValueError("neck area, radius, and hole_count are inconsistent")

    correction_coefficient = _positive(
        end_correction_coefficient,
        "end_correction_coefficient",
        allow_zero=True,
    )
    end_correction = correction_coefficient * radius
    effective_length = neck_length + end_correction
    if effective_length <= 0.0:
        return _zero_resonator(
            "lumped_helmholtz", "effective neck length must be positive"
        )

    if quality_factor is not None and loss_factor is not None:
        raise ValueError("specify quality_factor or loss_factor, not both")
    geometric_q = (
        2.0
        * math.pi
        * (sound_speed / (2.0 * math.pi))
        * math.sqrt(total_area / (cavity_volume * effective_length))
        * cavity_volume
        / (sound_speed * total_area)
    )
    if quality_factor is not None:
        q_value = _positive(quality_factor, "quality_factor")
        loss_model = "user-specified quality factor"
    elif loss_factor is not None:
        damping = _positive(loss_factor, "loss_factor")
        q_value = 1.0 / (2.0 * damping)
        loss_model = "Q = 1/(2*loss_factor)"
    else:
        q_value = min(50.0, max(0.5, geometric_q))
        loss_model = "bounded lumped geometric Q estimate"
    peak = _finite(peak_absorption, "peak_absorption")
    if not 0.0 <= peak <= 1.0:
        raise ValueError("peak_absorption must be in [0, 1]")

    f0 = (sound_speed / (2.0 * math.pi)) * math.sqrt(
        total_area / (cavity_volume * effective_length)
    )
    alpha: dict[str, float] = {}
    for band in BANDAS_OCTAVA:
        frequency = float(band)
        detuning = frequency / f0 - f0 / frequency
        alpha[band] = round(_bounded(peak / (1.0 + (q_value * detuning) ** 2)), 4)

    actual_open_ratio = ratio
    if actual_open_ratio is None and panel_area is not None:
        actual_open_ratio = total_area / panel_area
    return {
        "model": "lumped_helmholtz",
        "f0": round(f0, 1),
        "alpha": alpha,
        "Q": round(q_value, 3),
        "peak_absorption": peak,
        "neck_area_m2": total_area,
        "neck_radius_m": radius,
        "effective_hole_count": round(geometric_count, 3),
        "hole_count": hole_count,
        "panel_area_m2": panel_area,
        "open_area_ratio": actual_open_ratio,
        "neck_length_m": neck_length,
        "end_correction_m": end_correction,
        "end_correction_coefficient": correction_coefficient,
        "effective_neck_length_m": effective_length,
        "loss_model": loss_model,
        "assumptions": [
            "Lumped, acoustically compact cavity and neck are assumed.",
            "End correction is coefficient times the radius of each opening.",
            "The octave-band Lorentzian curve is an engineering estimate.",
        ],
        "estimate_label": ESTIMATE_LABEL,
    }


def membrane_absorber(
    mass_per_area_kgm2: float,
    air_gap_m: float,
    *,
    quality_factor: float | None = None,
    loss_factor: float | None = None,
    surface_tension_n_m: float = 0.0,
    panel_span_m: float | None = None,
    peak_absorption: float = 0.9,
) -> dict:
    """Estimate a panel/membrane absorber with explicit loss/tension choices."""

    try:
        mass = _positive(mass_per_area_kgm2, "mass_per_area_kgm2")
        gap = _positive(air_gap_m, "air_gap_m")
    except (TypeError, ValueError) as exc:
        return _zero_resonator("membrane_panel_estimate", str(exc))

    tension = _positive(
        surface_tension_n_m,
        "surface_tension_n_m",
        allow_zero=True,
    )
    air_spring_f0 = 60.0 / math.sqrt(mass * gap)
    tension_f0 = 0.0
    if tension > 0.0:
        if panel_span_m is None:
            raise ValueError("panel_span_m is required when surface tension is used")
        span = _positive(panel_span_m, "panel_span_m")
        tension_f0 = math.sqrt(2.0 * tension / mass) / (2.0 * span)
    else:
        span = panel_span_m
        if span is not None:
            span = _positive(span, "panel_span_m")
    f0 = math.hypot(air_spring_f0, tension_f0)

    if quality_factor is not None and loss_factor is not None:
        raise ValueError("specify quality_factor or loss_factor, not both")
    if quality_factor is not None:
        q_value = _positive(quality_factor, "quality_factor")
        loss_model = "user-specified quality factor"
    elif loss_factor is not None:
        damping = _positive(loss_factor, "loss_factor")
        q_value = 1.0 / (2.0 * damping)
        loss_model = "Q = 1/(2*loss_factor)"
    else:
        q_value = 5.0
        loss_model = "assumed Q=5; construction losses not supplied"
    peak = _finite(peak_absorption, "peak_absorption")
    if not 0.0 <= peak <= 1.0:
        raise ValueError("peak_absorption must be in [0, 1]")

    alpha: dict[str, float] = {}
    for band in BANDAS_OCTAVA:
        frequency = float(band)
        detuning = frequency / f0 - f0 / frequency
        alpha[band] = round(_bounded(peak / (1.0 + (q_value * detuning) ** 2)), 4)
    return {
        "model": "membrane_panel_estimate",
        "f0": round(f0, 1),
        "air_spring_f0_hz": round(air_spring_f0, 2),
        "tension_f0_hz": round(tension_f0, 2),
        "alpha": alpha,
        "Q": round(q_value, 3),
        "peak_absorption": peak,
        "surface_tension_n_m": tension,
        "panel_span_m": span,
        "loss_model": loss_model,
        "assumptions": [
            "The 60/sqrt(mass*depth) air-spring relation is empirical.",
            "A square fundamental membrane mode is combined in quadrature when tension is supplied.",
            "Leakage, edge restraint, porous infill, and structural damping require measured inputs.",
        ],
        "estimate_label": ESTIMATE_LABEL,
    }


def recommended_absorber_area(
    absorption_coefficients: Mapping[str, float],
    missing_absorption_m2_sabins: Mapping[str, float],
    *,
    existing_surface_alpha: Mapping[str, float] | None = None,
    installation_mode: str = "added",
    available_area_m2: float | None = None,
) -> dict:
    """Convert per-band missing absorption into one governing absorber area.

    Frequencies are constraints, never additive quantities.  The recommended
    area is the maximum per-band area.  In replacement mode the usable
    coefficient is ``alpha_new - alpha_existing``.
    """

    if installation_mode not in {"added", "replacement"}:
        raise ValueError("installation_mode must be 'added' or 'replacement'")
    existing = existing_surface_alpha or {}
    effective: dict[str, float] = {}
    missing: dict[str, float] = {}
    per_band: dict[str, float | None] = {}
    impossible: list[str] = []
    for band in BANDAS_OCTAVA:
        coefficient = _finite(absorption_coefficients.get(band, 0.0), f"alpha[{band}]")
        if not 0.0 <= coefficient <= 1.0:
            raise ValueError(f"alpha[{band}] must be in [0, 1]")
        baseline = _finite(existing.get(band, 0.0), f"existing_alpha[{band}]")
        if not 0.0 <= baseline <= 1.0:
            raise ValueError(f"existing_alpha[{band}] must be in [0, 1]")
        deficit = _finite(
            missing_absorption_m2_sabins.get(band, 0.0),
            f"missing_absorption[{band}]",
        )
        if deficit < 0.0:
            raise ValueError(f"missing_absorption[{band}] must be non-negative")
        gain = coefficient if installation_mode == "added" else coefficient - baseline
        effective[band] = round(gain, 6)
        missing[band] = deficit
        if deficit == 0.0:
            per_band[band] = 0.0
        elif gain <= 0.0:
            per_band[band] = None
            impossible.append(band)
        else:
            per_band[band] = deficit / gain

    finite_areas = [area for area in per_band.values() if area is not None]
    recommended = None if impossible else max(finite_areas, default=0.0)
    if available_area_m2 is None:
        available = None
        applied_area = recommended
    else:
        available = _positive(available_area_m2, "available_area_m2", allow_zero=True)
        applied_area = available if recommended is None else min(recommended, available)

    applied = applied_area or 0.0
    remaining = {
        band: round(max(0.0, missing[band] - applied * max(0.0, effective[band])), 6)
        for band in BANDAS_OCTAVA
    }
    feasible = recommended is not None and (
        available is None or recommended <= available + 1e-9
    )
    governing = []
    if recommended is not None:
        governing = [
            band
            for band, area in per_band.items()
            if area is not None and math.isclose(area, recommended, rel_tol=1e-9, abs_tol=1e-9)
        ]
    return {
        "recommended_area_m2": None if recommended is None else round(recommended, 3),
        "available_area_m2": available,
        "feasible": feasible,
        "installation_mode": installation_mode,
        "effective_absorption_coefficients": effective,
        "per_band_area_m2": {
            band: None if area is None else round(area, 3)
            for band, area in per_band.items()
        },
        "governing_bands": governing,
        "impossible_bands": impossible,
        "remaining_missing_absorption_m2_sabins": remaining,
        "constraint_rule": "maximum per-band area; Sabins are not summed across frequencies",
        "estimate_label": ESTIMATE_LABEL,
    }

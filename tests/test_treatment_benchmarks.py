"""Small public-reference arithmetic benchmarks for the Phase 3 core."""

import pytest

from acoustic_core.absorbers import porous_absorber_estimate
from acoustic_core.diffusers import polar_diffusion_coefficient
from acoustic_core.inverse import verify_treatment_plan
from acoustic_core.models import BANDAS_OCTAVA, Material
from acoustic_core.presets import calculate_air_attenuation, iso11654_diagnostics


def test_iso11654_reference_curve_shift_benchmark():
    practical = {
        "250": 0.35,
        "500": 0.60,
        "1000": 0.85,
        "2000": 0.90,
        "4000": 0.90,
    }
    result = iso11654_diagnostics(practical)

    # At alpha_w=0.65 the shifted 250/500 Hz values are 0.45/0.65,
    # giving unfavorable deviations 0.10+0.05=0.15, so that position fails.
    rejected_sum_at_065 = max(0, 0.45 - practical["250"]) + max(
        0, 0.65 - practical["500"]
    )
    assert rejected_sum_at_065 == pytest.approx(0.15)
    assert result.alpha_w == pytest.approx(0.60)
    assert result.unfavorable_deviation_sum == pytest.approx(0.05)


def test_iso9613_air_attenuation_20c_50rh_regression():
    result = calculate_air_attenuation(1000, 50, 20)
    assert result.attenuation_db_per_m == pytest.approx(0.0046647319, rel=1e-7)
    assert result.energy_decay_m_inv == pytest.approx(0.0010740942, rel=1e-7)


def test_delany_bazley_dimensionless_range_benchmark():
    result = porous_absorber_estimate(0.05, 10000, density_kgm3=None)
    # X = rho_air*f/sigma = 1.2*125/10000 = 0.015.
    assert result["validity_parameter_rho_f_over_sigma"]["125"] == pytest.approx(0.015)
    assert result["valid_by_band"]["125"] is True


def test_iso17497_style_normalized_diffusion_arithmetic():
    # Linear pressure maps to energy before applying the public polar formula.
    # E=[1,.25,.25,0]: ((1.5)^2-1.125)/(3*1.125) = 1/3.
    assert polar_diffusion_coefficient([1, 0.5, 0.5, 0]) == pytest.approx(1 / 3)


def test_forward_verification_matches_manual_sabine(sala_basica):
    treatment = Material(nombre="benchmark", alpha_unico=0.55)
    result = verify_treatment_plan(
        sala_basica,
        {band: 1.0 for band in BANDAS_OCTAVA},
        [{
            "material": treatment,
            "area_m2": 10,
            "surface_index": 0,
            "installation_mode": "replacement",
        }],
    )
    expected_absorption = 94 * 0.05 + 10 * (0.55 - 0.05)
    assert result["predicted_absorption_m2_sabins"]["1000"] == pytest.approx(
        expected_absorption
    )
    assert result["predicted_rt60_s"]["1000"] == pytest.approx(
        0.161 * 60 / expected_absorption,
        abs=1e-4,
    )

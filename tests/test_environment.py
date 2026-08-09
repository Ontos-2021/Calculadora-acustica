from dataclasses import FrozenInstanceError
import math

import pytest

from acoustic_core.environment import Environment, calculate_sound_speed


class TestSoundSpeed:
    def test_dry_air_temperature_reference_formula(self):
        environment = Environment(temperature_c=20, relative_humidity=0)
        expected = 331.3 * math.sqrt(293.15 / 273.15)
        assert environment.sound_speed_m_s == pytest.approx(expected, rel=1e-15)
        assert environment.sound_speed == environment.speed_of_sound

    def test_documented_humidity_correction(self):
        dry = Environment(temperature_c=20, relative_humidity=0).sound_speed_m_s
        saturated = Environment(temperature_c=20, relative_humidity=100).sound_speed_m_s
        assert saturated - dry == pytest.approx(1.24, rel=1e-14)

    def test_public_function_uses_same_validated_contract(self):
        assert calculate_sound_speed(10, 40, 90_000) == pytest.approx(
            Environment(10, 40, 90_000).sound_speed_m_s
        )

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"temperature_c": -273.15},
            {"relative_humidity": -0.1},
            {"relative_humidity": 100.1},
            {"pressure_pa": 0},
            {"temperature_c": math.nan},
        ],
    )
    def test_invalid_environment_is_rejected(self, kwargs):
        with pytest.raises(ValueError):
            Environment(**kwargs)

    def test_environment_is_immutable(self):
        environment = Environment()
        with pytest.raises(FrozenInstanceError):
            environment.temperature_c = 30


class TestAtmosphericAttenuation:
    def test_iso_9613_reference_values_at_standard_conditions(self):
        environment = Environment(20, 50, 101_325)
        assert environment.air_attenuation_db_per_m(1000) == pytest.approx(
            0.004664731873821475,
            rel=1e-12,
        )
        assert environment.air_attenuation_db_per_m(4000) == pytest.approx(
            0.029665528426392616,
            rel=1e-12,
        )

    def test_db_and_energy_decay_coefficients_are_consistent(self):
        environment = Environment()
        db_per_m = environment.air_attenuation_db_per_m(2000)
        assert environment.air_attenuation_m_inv(2000) == pytest.approx(
            db_per_m * math.log(10) / 10
        )

    def test_non_positive_frequency_is_rejected(self):
        with pytest.raises(ValueError):
            Environment().air_attenuation_db_per_m(0)

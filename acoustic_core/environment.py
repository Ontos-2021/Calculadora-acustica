"""Validated environmental conditions used by acoustic calculations."""

from __future__ import annotations

from dataclasses import dataclass
import math


REFERENCE_PRESSURE_PA = 101_325.0
REFERENCE_TEMPERATURE_K = 293.15


def _finite(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class Environment:
    """Atmospheric state.

    ``relative_humidity`` is expressed as a percentage from 0 to 100.  Sound
    speed uses the standard square-root dry-air temperature relation plus the
    common 0.0124 m/s per percentage-point humidity approximation.  The speed
    of an ideal gas is pressure-independent at fixed temperature; pressure is
    retained for atmospheric attenuation calculations.
    """

    temperature_c: float = 20.0
    relative_humidity: float = 50.0
    pressure_pa: float = REFERENCE_PRESSURE_PA

    def __post_init__(self) -> None:
        temperature = _finite(self.temperature_c, "temperature_c")
        humidity = _finite(self.relative_humidity, "relative_humidity")
        pressure = _finite(self.pressure_pa, "pressure_pa")
        if temperature <= -273.15:
            raise ValueError("temperature_c must be above absolute zero")
        if not 0.0 <= humidity <= 100.0:
            raise ValueError("relative_humidity must be between 0 and 100 percent")
        if pressure <= 0.0:
            raise ValueError("pressure_pa must be positive")
        object.__setattr__(self, "temperature_c", temperature)
        object.__setattr__(self, "relative_humidity", humidity)
        object.__setattr__(self, "pressure_pa", pressure)

    @property
    def temperature_k(self) -> float:
        return self.temperature_c + 273.15

    @property
    def relative_humidity_percent(self) -> float:
        return self.relative_humidity

    @property
    def sound_speed_m_s(self) -> float:
        dry_air = 331.3 * math.sqrt(self.temperature_k / 273.15)
        return dry_air + 0.0124 * self.relative_humidity

    @property
    def sound_speed(self) -> float:
        return self.sound_speed_m_s

    @property
    def speed_of_sound(self) -> float:
        return self.sound_speed_m_s

    def air_attenuation_db_per_m(self, frequency_hz: float) -> float:
        """Return atmospheric attenuation using ISO 9613-1 equations."""

        frequency = _finite(frequency_hz, "frequency_hz")
        if frequency <= 0.0:
            raise ValueError("frequency_hz must be positive")

        temperature = self.temperature_k
        pressure_ratio = self.pressure_pa / REFERENCE_PRESSURE_PA
        temperature_ratio = temperature / REFERENCE_TEMPERATURE_K

        saturation_pressure_ratio = 10.0 ** (
            -6.8346 * (273.16 / temperature) ** 1.261 + 4.6151
        )
        water_vapor_concentration = (
            self.relative_humidity * saturation_pressure_ratio / pressure_ratio
        )

        oxygen_relaxation = pressure_ratio * (
            24.0
            + 4.04e4
            * water_vapor_concentration
            * (0.02 + water_vapor_concentration)
            / (0.391 + water_vapor_concentration)
        )
        nitrogen_relaxation = (
            pressure_ratio
            * temperature_ratio**-0.5
            * (
                9.0
                + 280.0
                * water_vapor_concentration
                * math.exp(-4.17 * (temperature_ratio ** (-1.0 / 3.0) - 1.0))
            )
        )

        classical = 1.84e-11 * pressure_ratio**-1.0 * temperature_ratio**0.5
        molecular = temperature_ratio**-2.5 * (
            0.01275
            * math.exp(-2239.1 / temperature)
            / (oxygen_relaxation + frequency * frequency / oxygen_relaxation)
            + 0.1068
            * math.exp(-3352.0 / temperature)
            / (nitrogen_relaxation + frequency * frequency / nitrogen_relaxation)
        )
        attenuation = 8.686 * frequency * frequency * (classical + molecular)
        if not math.isfinite(attenuation) or attenuation < 0.0:
            raise ValueError("environment produced an invalid air attenuation")
        return attenuation

    def air_attenuation_m_inv(self, frequency_hz: float) -> float:
        """Return the equivalent energy-decay coefficient in inverse metres."""

        return self.air_attenuation_db_per_m(frequency_hz) * math.log(10.0) / 10.0


STANDARD_ENVIRONMENT = Environment()


def calculate_sound_speed(
    temperature_c: float = 20.0,
    relative_humidity: float = 50.0,
    pressure_pa: float = REFERENCE_PRESSURE_PA,
) -> float:
    """Calculate sound speed in m/s from validated environmental inputs."""

    return Environment(temperature_c, relative_humidity, pressure_pa).sound_speed_m_s


speed_of_sound = calculate_sound_speed

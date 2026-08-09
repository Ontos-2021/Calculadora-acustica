"""Immutable contracts for fractional-octave spectral data.

The nominal center frequencies follow the preferred IEC 61260 labels.  Exact
geometric centers are retained alongside those labels so calculations such as
band-edge classification do not inherit the rounding in nominal labels.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
import math
from types import MappingProxyType


Number = int | float


def _finite_float(value: Number, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field} must be a real number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{field} must be finite")
    return converted


@dataclass(frozen=True, slots=True)
class FrequencyBands:
    """A validated ordered set of nominal fractional-octave centers."""

    name: str
    centers_hz: tuple[float, ...]
    bands_per_octave: int
    exact_centers_hz: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):
            raise TypeError("band-set name must be a string")
        name = self.name.strip()
        if not name:
            raise ValueError("band-set name must not be empty")
        if (
            isinstance(self.bands_per_octave, bool)
            or not isinstance(self.bands_per_octave, int)
            or self.bands_per_octave <= 0
        ):
            raise ValueError("bands_per_octave must be a positive integer")

        centers = tuple(_finite_float(v, "band center") for v in self.centers_hz)
        if not centers:
            raise ValueError("a band set must contain at least one center")
        if any(center <= 0 for center in centers):
            raise ValueError("band centers must be positive")
        if any(left >= right for left, right in zip(centers, centers[1:])):
            raise ValueError("band centers must be strictly increasing")

        exact = self.exact_centers_hz or centers
        exact = tuple(_finite_float(v, "exact band center") for v in exact)
        if len(exact) != len(centers):
            raise ValueError("nominal and exact center sets must have equal length")
        if any(center <= 0 for center in exact):
            raise ValueError("exact band centers must be positive")
        if any(left >= right for left, right in zip(exact, exact[1:])):
            raise ValueError("exact band centers must be strictly increasing")

        object.__setattr__(self, "name", name)
        object.__setattr__(self, "centers_hz", centers)
        object.__setattr__(self, "exact_centers_hz", exact)

    def __iter__(self) -> Iterator[float]:
        return iter(self.centers_hz)

    def __len__(self) -> int:
        return len(self.centers_hz)

    def index(self, center_hz: Number) -> int:
        center = _finite_float(center_hz, "center_hz")
        try:
            return self.centers_hz.index(center)
        except ValueError as exc:
            raise KeyError(f"{center_hz} Hz is not in {self.name}") from exc

    def edges(self, center_hz: Number) -> tuple[float, float]:
        """Return exact lower-inclusive and upper-exclusive band edges."""

        index = self.index(center_hz)
        ratio = 2.0 ** (1.0 / (2.0 * self.bands_per_octave))
        exact_center = self.exact_centers_hz[index]
        return exact_center / ratio, exact_center * ratio


OCTAVE_BAND_CENTERS_HZ = (
    31.5,
    63.0,
    125.0,
    250.0,
    500.0,
    1000.0,
    2000.0,
    4000.0,
    8000.0,
    16000.0,
)
OCTAVE_BAND_EXACT_CENTERS_HZ = tuple(
    1000.0 * 2.0**index for index in range(-5, 5)
)

THIRD_OCTAVE_BAND_CENTERS_HZ = (
    20.0,
    25.0,
    31.5,
    40.0,
    50.0,
    63.0,
    80.0,
    100.0,
    125.0,
    160.0,
    200.0,
    250.0,
    315.0,
    400.0,
    500.0,
    630.0,
    800.0,
    1000.0,
    1250.0,
    1600.0,
    2000.0,
    2500.0,
    3150.0,
    4000.0,
    5000.0,
    6300.0,
    8000.0,
    10000.0,
    12500.0,
    16000.0,
    20000.0,
)
THIRD_OCTAVE_BAND_EXACT_CENTERS_HZ = tuple(
    1000.0 * 2.0 ** (index / 3.0) for index in range(-17, 14)
)

ROOM_OCTAVE_BAND_CENTERS_HZ = (125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0)
ROOM_OCTAVE_BAND_EXACT_CENTERS_HZ = tuple(
    1000.0 * 2.0**index for index in range(-3, 3)
)

OCTAVE_BANDS = FrequencyBands(
    name="standard octave bands",
    centers_hz=OCTAVE_BAND_CENTERS_HZ,
    exact_centers_hz=OCTAVE_BAND_EXACT_CENTERS_HZ,
    bands_per_octave=1,
)
THIRD_OCTAVE_BANDS = FrequencyBands(
    name="standard one-third-octave bands",
    centers_hz=THIRD_OCTAVE_BAND_CENTERS_HZ,
    exact_centers_hz=THIRD_OCTAVE_BAND_EXACT_CENTERS_HZ,
    bands_per_octave=3,
)
ROOM_OCTAVE_BANDS = FrequencyBands(
    name="architectural octave bands",
    centers_hz=ROOM_OCTAVE_BAND_CENTERS_HZ,
    exact_centers_hz=ROOM_OCTAVE_BAND_EXACT_CENTERS_HZ,
    bands_per_octave=1,
)

# Explicit aliases make the standard represented by each exported value clear.
STANDARD_OCTAVE_BANDS = OCTAVE_BANDS
STANDARD_THIRD_OCTAVE_BANDS = THIRD_OCTAVE_BANDS
ONE_THIRD_OCTAVE_BANDS = THIRD_OCTAVE_BANDS


@dataclass(frozen=True, slots=True)
class Spectrum:
    """Immutable values over one exact :class:`FrequencyBands` contract."""

    bands: FrequencyBands
    values: tuple[float, ...]
    unit: str
    name: str
    provenance: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.bands, FrequencyBands):
            raise TypeError("bands must be a FrequencyBands instance")
        values = tuple(_finite_float(value, "spectral value") for value in self.values)
        if len(values) != len(self.bands):
            raise ValueError(
                f"{self.bands.name} requires exactly {len(self.bands)} values; "
                f"received {len(values)}"
            )
        if not isinstance(self.unit, str) or not isinstance(self.name, str):
            raise TypeError("spectrum unit and name must be strings")
        if self.provenance is not None and not isinstance(self.provenance, str):
            raise TypeError("spectrum provenance must be a string when provided")
        unit = self.unit.strip()
        name = self.name.strip()
        if not unit:
            raise ValueError("spectrum unit must not be empty")
        if not name:
            raise ValueError("spectrum name must not be empty")
        provenance = self.provenance.strip() if self.provenance is not None else None
        if provenance == "":
            raise ValueError("provenance must not be empty when provided")

        object.__setattr__(self, "values", values)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "provenance", provenance)

    @classmethod
    def from_mapping(
        cls,
        values: Mapping[Number | str, Number],
        *,
        bands: FrequencyBands,
        unit: str,
        name: str,
        provenance: str | None = None,
    ) -> Spectrum:
        """Build a spectrum, rejecting every missing, duplicate, or extra band."""

        normalized: dict[float, float] = {}
        for raw_center, raw_value in values.items():
            if isinstance(raw_center, str):
                try:
                    center = float(raw_center)
                except ValueError as exc:
                    raise ValueError(f"invalid band center: {raw_center!r}") from exc
            else:
                center = _finite_float(raw_center, "band center")
            if not math.isfinite(center):
                raise ValueError("band centers must be finite")
            if center in normalized:
                raise ValueError(f"duplicate band center: {center:g} Hz")
            normalized[center] = _finite_float(raw_value, f"value at {center:g} Hz")

        expected = set(bands.centers_hz)
        actual = set(normalized)
        if actual != expected:
            missing = sorted(expected - actual)
            unknown = sorted(actual - expected)
            details = []
            if missing:
                details.append(f"missing={missing}")
            if unknown:
                details.append(f"unknown={unknown}")
            raise ValueError(f"band set does not match {bands.name}: {', '.join(details)}")

        return cls(
            bands=bands,
            values=tuple(normalized[center] for center in bands.centers_hz),
            unit=unit,
            name=name,
            provenance=provenance,
        )

    def value_at(self, center_hz: Number) -> float:
        return self.values[self.bands.index(center_hz)]

    def as_mapping(self) -> Mapping[float, float]:
        return MappingProxyType(dict(zip(self.bands.centers_hz, self.values)))

    def as_dict(self) -> dict[float, float]:
        return dict(zip(self.bands.centers_hz, self.values))

    def with_values(self, values: Sequence[Number], *, name: str | None = None) -> Spectrum:
        return Spectrum(
            bands=self.bands,
            values=tuple(values),
            unit=self.unit,
            name=name or self.name,
            provenance=self.provenance,
        )


# Domain-friendly synonym for callers that prefer an explicit contract name.
BandSpectrum = Spectrum

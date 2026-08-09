"""Small immutable uncertainty metadata contract."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class Uncertainty:
    """A non-negative standard uncertainty with optional coverage metadata."""

    value: float
    unit: str = "1"
    coverage_factor: float = 1.0
    confidence_level: float | None = None
    source: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, (int, float)):
            raise TypeError("uncertainty value must be a real number")
        if isinstance(self.coverage_factor, bool) or not isinstance(
            self.coverage_factor, (int, float)
        ):
            raise TypeError("coverage_factor must be a real number")
        value = float(self.value)
        coverage = float(self.coverage_factor)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("uncertainty value must be finite and non-negative")
        if not math.isfinite(coverage) or coverage <= 0.0:
            raise ValueError("coverage_factor must be finite and positive")
        if not math.isfinite(value * coverage):
            raise ValueError("expanded uncertainty must be finite")
        if not isinstance(self.unit, str):
            raise TypeError("uncertainty unit must be a string")
        if not self.unit.strip():
            raise ValueError("uncertainty unit must not be empty")
        confidence = self.confidence_level
        if confidence is not None:
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
                raise TypeError("confidence_level must be a real number")
            confidence = float(confidence)
            if not math.isfinite(confidence) or not 0.0 < confidence <= 1.0:
                raise ValueError("confidence_level must be in (0, 1]")
        if self.source is not None and not isinstance(self.source, str):
            raise TypeError("source must be a string when provided")
        source = self.source.strip() if self.source is not None else None
        if source == "":
            raise ValueError("source must not be empty when provided")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "coverage_factor", coverage)
        object.__setattr__(self, "confidence_level", confidence)
        object.__setattr__(self, "unit", self.unit.strip())
        object.__setattr__(self, "source", source)

    @property
    def expanded(self) -> float:
        return self.value * self.coverage_factor

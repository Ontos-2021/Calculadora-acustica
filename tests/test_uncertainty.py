from dataclasses import FrozenInstanceError
import math

import pytest

from acoustic_core.uncertainty import Uncertainty


def test_expanded_uncertainty_reference_calculation():
    uncertainty = Uncertainty(
        value=0.02,
        unit="m",
        coverage_factor=2.0,
        confidence_level=0.95,
        source="calibration certificate",
    )
    assert uncertainty.expanded == pytest.approx(0.04)
    assert uncertainty.confidence_level == 0.95


@pytest.mark.parametrize(
    "kwargs",
    [
        {"value": -0.1},
        {"value": math.inf},
        {"value": 0.1, "coverage_factor": 0},
        {"value": 0.1, "confidence_level": 0},
        {"value": 0.1, "confidence_level": 1.1},
        {"value": 0.1, "unit": ""},
        {"value": 1e308, "coverage_factor": 2.0},
    ],
)
def test_invalid_uncertainty_metadata_is_rejected(kwargs):
    with pytest.raises(ValueError):
        Uncertainty(**kwargs)


def test_uncertainty_is_immutable():
    uncertainty = Uncertainty(0.1)
    with pytest.raises(FrozenInstanceError):
        uncertainty.value = 0.2

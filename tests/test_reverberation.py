import math

import pytest

from acoustic_core.models import BANDAS_OCTAVA, Material, Room, Surface
from acoustic_core.reverberation import (
    RT60_UNBOUNDED_SENTINEL,
    SabineApplicabilityWarning,
    calculate_rt60,
    calculate_rt60_result,
    rt60_eyring,
    rt60_fitzroy,
    rt60_millington,
    rt60_promedio_sabine,
    rt60_sabine,
)


AREAS = (12.0, 12.0, 15.0, 15.0, 20.0, 20.0)


def _room(alpha: float) -> Room:
    material = Material(nombre=f"alpha={alpha}", alpha_unico=alpha)
    surfaces = [
        Surface(nombre=str(index), area=area, material=material)
        for index, area in enumerate(AREAS)
    ]
    return Room(largo=5.0, ancho=4.0, alto=3.0, superficies=surfaces)


class TestReferenceFormulas:
    def test_sabine_matches_closed_form_at_uniform_absorption(self):
        room = _room(0.05)
        expected = 0.161 * 60.0 / (94.0 * 0.05)
        result = rt60_sabine(room, "500")
        assert result == pytest.approx(expected, rel=1e-14)
        assert result != round(result, 2)

    def test_eyring_millington_and_fitzroy_converge_for_uniform_room(self):
        room = _room(0.1)
        expected = 0.161 * 60.0 / (-94.0 * math.log1p(-0.1))
        assert rt60_eyring(room, "500") == pytest.approx(expected, rel=1e-14)
        assert rt60_millington(room, "500") == pytest.approx(expected, rel=1e-14)
        assert rt60_fitzroy(room, "500") == pytest.approx(expected, rel=1e-14)

    def test_mean_sabine_matches_uniform_band_result(self):
        room = _room(0.05)
        assert rt60_promedio_sabine(room) == pytest.approx(rt60_sabine(room, "500"))


class TestAbsorptionEdges:
    @pytest.mark.parametrize(
        "method",
        [rt60_sabine, rt60_eyring, rt60_millington, rt60_fitzroy],
    )
    def test_zero_absorption_is_explicitly_unbounded(self, method):
        assert math.isinf(method(_room(0.0), "500"))

    def test_perfect_absorption_limits(self):
        room = _room(1.0)
        with pytest.warns(SabineApplicabilityWarning):
            sabine = rt60_sabine(room, "500")
        assert sabine == pytest.approx(0.161 * 60.0 / 94.0)
        assert rt60_eyring(room, "500") == 0.0
        assert rt60_millington(room, "500") == 0.0
        assert rt60_fitzroy(room, "500") == 0.0

    def test_legacy_aggregate_never_exposes_infinity(self):
        with pytest.warns(RuntimeWarning):
            result = calculate_rt60(_room(0.0))
        values = [value for methods in result.values() for value in methods.values()]
        assert values
        assert all(math.isfinite(value) for value in values)
        assert set(values) == {RT60_UNBOUNDED_SENTINEL}

    def test_structured_aggregate_uses_optional_value_and_diagnostic(self):
        result = calculate_rt60_result(_room(0.0))
        estimate = result.get("500", "Eyring")
        assert estimate.value_seconds is None
        assert not estimate.is_bounded
        assert "unbounded" in estimate.warnings[0]


class TestApplicabilityAndAir:
    def test_sabine_warns_above_mean_alpha_point_two(self):
        with pytest.warns(SabineApplicabilityWarning, match="500 Hz"):
            rt60_sabine(_room(0.3), "500")

    def test_warning_is_available_per_band_in_structured_result(self):
        result = calculate_rt60_result(_room(0.3))
        warnings_500 = result.get("500", "Sabine").warnings
        assert len(warnings_500) == 1
        assert "mean absorption=0.3" in warnings_500[0]

    def test_air_attenuation_reduces_rt60(self):
        room = _room(0.05)
        without_air = rt60_eyring(room, "4000")
        with_air = rt60_eyring(room, "4000", include_air_attenuation=True)
        assert with_air < without_air

    def test_air_attenuation_bounds_an_otherwise_lossless_room(self):
        room = _room(0.0)
        value = rt60_sabine(room, "4000", include_air_attenuation=True)
        expected = 0.161 / (4.0 * room.environment.air_attenuation_m_inv(4000.0))
        assert value == pytest.approx(expected)
        assert math.isfinite(value)


class TestAggregateShape:
    def test_all_bands_and_methods_are_preserved(self, sala_basica):
        result = calculate_rt60(sala_basica)
        assert list(result) == BANDAS_OCTAVA
        assert all(
            set(methods) == {"Sabine", "Eyring", "Millington", "FitzRoy"}
            for methods in result.values()
        )

    def test_unknown_band_is_not_silently_zero(self, sala_basica):
        with pytest.raises(ValueError, match="Banda desconocida"):
            rt60_sabine(sala_basica, "999")

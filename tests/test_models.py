import math

import pytest

from acoustic_core.environment import Environment
from acoustic_core.models import (
    BANDAS_OCTAVA,
    Material,
    Mode,
    ModeType,
    PartialAbsorptionWarning,
    Room,
    Surface,
)
from acoustic_core.uncertainty import Uncertainty


FULL_ALPHA = {band: 0.1 + index * 0.1 for index, band in enumerate(BANDAS_OCTAVA)}


class TestMaterial:
    def test_single_alpha_completes_every_band(self):
        material = Material(nombre="Test", alpha_unico=0.3)
        assert material.alpha == {band: 0.3 for band in BANDAS_OCTAVA}

    def test_complete_band_values_preserve_standard_order(self):
        material = Material(nombre="Test", alphas=dict(reversed(FULL_ALPHA.items())))
        assert list(material.alpha) == BANDAS_OCTAVA
        assert material.alpha == FULL_ALPHA

    def test_partial_values_infer_and_report_nonzero_baseline(self):
        with pytest.warns(PartialAbsorptionWarning, match="inferred"):
            material = Material(nombre="Test", alphas={"125": 0.1, "500": 0.5})
        assert material.alpha_unico == pytest.approx(0.3)
        assert material.alpha["125"] == pytest.approx(0.1)
        assert material.alpha["500"] == pytest.approx(0.5)
        assert material.alpha["250"] == pytest.approx(0.3)

    def test_partial_values_override_single_alpha_baseline(self):
        material = Material(nombre="Test", alpha_unico=0.2, alphas={"125": 0.9})
        assert material.alpha["125"] == 0.9
        assert material.alpha["500"] == 0.2

    @pytest.mark.parametrize("value", [-0.01, 1.01, math.inf, math.nan])
    def test_alpha_must_be_finite_probability(self, value):
        with pytest.raises(ValueError):
            Material(nombre="Test", alpha_unico=value)

    def test_material_requires_absorption_data(self):
        with pytest.raises(ValueError):
            Material(nombre="Test")

    def test_unknown_band_is_rejected(self):
        with pytest.raises(ValueError, match="Banda desconocida"):
            Material(nombre="Test", alpha_unico=0.2, alphas={"9999": 0.5})

    def test_alpha_spectrum_is_complete_and_metadata_aware(self):
        uncertainty = Uncertainty(0.02, source="lab")
        material = Material(
            nombre="Panel",
            alpha_unico=0.25,
            provenance="ISO 354 report",
            uncertainty=uncertainty,
        )
        spectrum = material.alpha_spectrum
        assert spectrum.name == "Absorption coefficient - Panel"
        assert spectrum.unit == "1"
        assert spectrum.provenance == "ISO 354 report"
        assert spectrum.values == (0.25,) * 6
        assert material.uncertainty.expanded == pytest.approx(0.02)

    def test_presets_are_complete(self):
        from acoustic_core.presets import MATERIALES_PRESETS

        assert len(MATERIALES_PRESETS) >= 5
        assert all(set(material.alpha) == set(BANDAS_OCTAVA) for material in MATERIALES_PRESETS.values())


class TestRoom:
    def test_geometry(self, sala_basica):
        assert sala_basica.volumen == 60.0
        assert sala_basica.superficie_total == 94.0

    def test_default_environment_is_backward_compatible(self, sala_basica):
        assert sala_basica.environment == Environment()
        assert sala_basica.sound_speed == pytest.approx(Environment().sound_speed_m_s)

    def test_custom_environment_and_metadata(self, sala_basica):
        room = Room(
            largo=5,
            ancho=4,
            alto=3,
            superficies=sala_basica.superficies,
            environment={
                "temperature_c": 10,
                "relative_humidity": 40,
                "pressure_pa": 90_000,
            },
            provenance="laser survey",
            uncertainty={"value": 0.005, "unit": "m"},
        )
        assert room.environment.temperature_c == 10.0
        assert room.provenance == "laser survey"
        assert room.uncertainty.unit == "m"

    @pytest.mark.parametrize("dimension", [-1.0, math.inf, math.nan])
    def test_invalid_dimension(self, sala_basica, dimension):
        with pytest.raises(ValueError):
            Room(
                largo=dimension,
                ancho=4,
                alto=3,
                superficies=sala_basica.superficies,
            )

    def test_volume_overflow_is_rejected(self, sala_basica):
        with pytest.raises(ValueError, match="volumen"):
            Room(
                largo=1e200,
                ancho=1e200,
                alto=1e200,
                superficies=sala_basica.superficies,
            )

    def test_exactly_six_surfaces_required(self):
        with pytest.raises(ValueError):
            Room(largo=5, ancho=4, alto=3, superficies=[])

    def test_optional_use(self, sala_basica):
        room = Room(
            largo=5,
            ancho=4,
            alto=3,
            superficies=sala_basica.superficies,
            uso="home_studio",
        )
        assert room.uso == "home_studio"


class TestMode:
    def test_energy_weight_converts_decibels_to_power_ratio(self):
        mode = Mode(
            indices=[1, 1, 0],
            frecuencia=100.123456,
            tipo=ModeType.TANGENTIAL,
            peso_db=-3.0,
        )
        assert mode.frequency_hz == 100.123456
        assert mode.energy_weight == pytest.approx(10 ** (-3 / 10))

    @pytest.mark.parametrize("indices", [[0, 0, 0], [-1, 0, 0], [1, 0], [True, 0, 0]])
    def test_invalid_modal_indices(self, indices):
        with pytest.raises((TypeError, ValueError)):
            Mode(indices=indices, frecuencia=100, tipo=ModeType.AXIAL, peso_db=0)

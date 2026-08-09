from dataclasses import FrozenInstanceError
import math

import pytest

from acoustic_core.spectrum import (
    OCTAVE_BANDS,
    ROOM_OCTAVE_BANDS,
    THIRD_OCTAVE_BANDS,
    FrequencyBands,
    Spectrum,
)


class TestBandContracts:
    def test_standard_nominal_centers(self):
        assert OCTAVE_BANDS.centers_hz[2:8] == ROOM_OCTAVE_BANDS.centers_hz
        assert len(THIRD_OCTAVE_BANDS) == 31
        assert THIRD_OCTAVE_BANDS.centers_hz[0] == 20.0
        assert THIRD_OCTAVE_BANDS.centers_hz[-1] == 20_000.0

    def test_third_octave_edges_use_exact_geometric_center(self):
        lower, upper = THIRD_OCTAVE_BANDS.edges(1000.0)
        ratio = 2.0 ** (1.0 / 6.0)
        assert lower == pytest.approx(1000.0 / ratio, rel=1e-15)
        assert upper == pytest.approx(1000.0 * ratio, rel=1e-15)
        assert upper == THIRD_OCTAVE_BANDS.edges(1250.0)[0]

    @pytest.mark.parametrize(
        "centers",
        [(100.0, 100.0), (100.0, 50.0), (100.0, math.inf), ()],
    )
    def test_band_centers_must_be_finite_positive_and_ordered(self, centers):
        with pytest.raises(ValueError):
            FrequencyBands("invalid", centers, 1)


class TestSpectrum:
    def test_complete_mapping_preserves_band_order_and_metadata(self):
        mapping = {
            str(int(center)): index / 10
            for index, center in reversed(list(enumerate(ROOM_OCTAVE_BANDS.centers_hz)))
        }
        spectrum = Spectrum.from_mapping(
            mapping,
            bands=ROOM_OCTAVE_BANDS,
            unit="s",
            name="RT60",
            provenance="calculation",
        )
        assert spectrum.values == pytest.approx(tuple(index / 10 for index in range(6)))
        assert spectrum.unit == "s"
        assert spectrum.name == "RT60"
        assert spectrum.value_at(500) == pytest.approx(0.2)

    @pytest.mark.parametrize(
        "mapping",
        [
            {"125": 0.1},
            {
                "125": 0.1,
                "250": 0.2,
                "500": 0.3,
                "1000": 0.4,
                "2000": 0.5,
                "4000": 0.6,
                "8000": 0.7,
            },
        ],
    )
    def test_mapping_must_match_exact_band_set(self, mapping):
        with pytest.raises(ValueError, match="band set does not match"):
            Spectrum.from_mapping(
                mapping,
                bands=ROOM_OCTAVE_BANDS,
                unit="1",
                name="alpha",
            )

    def test_non_finite_value_is_rejected(self):
        with pytest.raises(ValueError, match="finite"):
            Spectrum(
                bands=ROOM_OCTAVE_BANDS,
                values=(0.1, 0.2, 0.3, 0.4, 0.5, math.nan),
                unit="1",
                name="alpha",
            )

    def test_contract_is_immutable_including_mapping_view(self):
        spectrum = Spectrum(
            bands=ROOM_OCTAVE_BANDS,
            values=(1, 2, 3, 4, 5, 6),
            unit="dB",
            name="level",
        )
        with pytest.raises(FrozenInstanceError):
            spectrum.name = "changed"
        with pytest.raises(TypeError):
            spectrum.as_mapping()[125.0] = 7.0

    def test_name_unit_and_exact_value_count_are_required(self):
        with pytest.raises(ValueError):
            Spectrum(ROOM_OCTAVE_BANDS, (1,) * 5, "dB", "level")
        with pytest.raises(ValueError):
            Spectrum(ROOM_OCTAVE_BANDS, (1,) * 6, "", "level")
        with pytest.raises(ValueError):
            Spectrum(ROOM_OCTAVE_BANDS, (1,) * 6, "dB", "")

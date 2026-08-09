import math
import struct

import pytest

from acoustic_core.measurement import (
    compute_spectrogram,
    ess_deconvolution,
    estimate_modal_q,
    fractional_octave_edges,
    fractional_octave_frequency_response,
    generate_ess,
    generate_wav_bytes,
    harmonic_impulse_positions,
    harmonic_separation_offsets,
    read_wav_bytes,
    calibrate_alpha,
)


def _convolve_short(signal, kernel):
    result = [0.0] * (len(signal) + len(kernel) - 1)
    for sample_index, sample in enumerate(signal):
        for tap_index, tap in enumerate(kernel):
            result[sample_index + tap_index] += sample * tap
    return result


class TestESSBenchmarks:
    def test_validation_fades_headroom_and_determinism(self):
        first = generate_ess(
            50, 3000, 0.25, 8000, amplitude=0.8,
            fade_in_s=0.005, fade_out_s=0.005,
        )
        second = generate_ess(
            50, 3000, 0.25, 8000, amplitude=0.8,
            fade_in_s=0.005, fade_out_s=0.005,
        )
        assert first == second
        assert len(first) == 2000
        assert first[0] == 0.0
        assert first[-1] == pytest.approx(0.0, abs=1e-14)
        assert max(abs(value) for value in first) <= 0.8

        with pytest.raises(ValueError, match="greater"):
            generate_ess(1000, 1000, 1, 8000)
        with pytest.raises(ValueError, match="Nyquist"):
            generate_ess(20, 4000, 1, 8000)

    def test_farina_deconvolution_recovers_spaced_signed_taps(self):
        sweep = generate_ess(
            100, 3000, 0.5, 8000,
            fade_in_s=0.005, fade_out_s=0.005,
        )
        expected = [1.0] + [0.0] * 12 + [0.4] + [0.0] * 9 + [-0.2]
        response = _convolve_short(sweep, expected)
        recovered = ess_deconvolution(response, sweep, 8000)

        assert len(recovered) == len(expected)
        assert recovered[0] == pytest.approx(1.0, abs=0.04)
        assert recovered[13] == pytest.approx(0.4, abs=0.06)
        assert recovered[23] == pytest.approx(-0.2, abs=0.05)

    def test_harmonic_separation_offsets_and_positions(self):
        offsets = harmonic_separation_offsets(20, 20000, 1.0, 44100, 5)
        assert offsets[2] == round(44100 * math.log(2) / math.log(1000))
        assert list(offsets.values()) == sorted(offsets.values())
        positions = harmonic_impulse_positions(20000, 20, 20000, 1.0, 44100, 5)
        assert positions[1] == 20000
        assert positions[3] == 20000 - offsets[3]


class TestWavBenchmarks:
    @pytest.mark.parametrize(
        "bit_depth, encoding, tolerance",
        [
            (16, "pcm", 4e-5),
            (24, "pcm", 2e-7),
            (32, "pcm", 1e-9),
            (32, "float32", 2e-7),
        ],
    )
    def test_multichannel_round_trip(self, bit_depth, encoding, tolerance):
        channels = [
            [0.0, -1.0, 0.25, 0.999],
            [0.5, -0.5, 0.75, -0.75],
        ]
        wav = generate_wav_bytes(
            channels, 48000, bit_depth=bit_depth, encoding=encoding,
        )
        parsed = read_wav_bytes(wav, channel=None)

        assert wav[36:40] == b"data"
        assert struct.unpack_from("<I", wav, 40)[0] == 4 * 2 * (bit_depth // 8)
        assert parsed["sample_rate"] == 48000
        assert parsed["num_channels"] == 2
        assert parsed["num_frames"] == 4
        for expected, recovered in zip(channels, parsed["samples"]):
            assert recovered == pytest.approx(expected, abs=tolerance)

    def test_unknown_odd_chunk_and_channel_mix(self):
        wav = generate_wav_bytes([[0.2, -0.2], [0.4, 0.2]], 8000)
        data_offset = wav.index(b"data")
        junk = b"JUNK" + struct.pack("<I", 3) + b"abc" + b"\x00"
        with_junk = wav[:data_offset] + junk + wav[data_offset:]
        with_junk = (
            with_junk[:4]
            + struct.pack("<I", len(with_junk) - 8)
            + with_junk[8:]
        )
        parsed = read_wav_bytes(with_junk, channel="mix")
        assert parsed["samples"] == pytest.approx([0.3, 0.0], abs=4e-5)

    def test_truncated_chunk_is_rejected(self):
        wav = bytearray(generate_wav_bytes([0.1], 8000))
        struct.pack_into("<I", wav, 40, 1000)
        with pytest.raises(ValueError, match="truncated"):
            read_wav_bytes(bytes(wav))


class TestAnalysisBenchmarks:
    @pytest.mark.parametrize("fraction", [1, 3])
    def test_fourth_order_filter_has_defined_minus_3db_edges(self, fraction):
        lower, upper = fractional_octave_edges(1000.0, fraction)
        magnitudes = fractional_octave_frequency_response(
            1000.0, 48000, [lower, 1000.0, upper], fraction,
        )
        assert 20 * math.log10(magnitudes[0]) == pytest.approx(-3.0103, abs=0.001)
        assert magnitudes[1] == pytest.approx(1.0, abs=1e-9)
        assert 20 * math.log10(magnitudes[2]) == pytest.approx(-3.0103, abs=0.001)

    def test_spectrogram_dimensions_and_tone_bin(self):
        sample_rate = 8000
        signal = [
            math.sin(2 * math.pi * 1000 * index / sample_rate)
            for index in range(1024)
        ]
        result = compute_spectrogram(signal, sample_rate, 256, 128)
        assert len(result["times_s"]) == 7
        assert len(result["frequencies_hz"]) == 129
        assert len(result["magnitude_db"]) == 7
        assert all(len(frame) == 129 for frame in result["magnitude_db"])
        peak_bin = max(
            range(129), key=lambda index: result["magnitude"][0][index]
        )
        assert result["frequencies_hz"][peak_bin] == pytest.approx(1000.0)

    def test_modal_q_ring_down(self):
        sample_rate = 8000
        frequency = 250.0
        expected_q = 25.0
        signal = [
            math.exp(-math.pi * frequency * index / sample_rate / expected_q)
            * math.sin(2 * math.pi * frequency * index / sample_rate)
            for index in range(sample_rate)
        ]
        result = estimate_modal_q(signal, sample_rate, frequency)
        assert result["Q"] == pytest.approx(expected_q, rel=0.01)
        assert result["r2"] > 0.999


class TestCalibrationBenchmarks:
    def test_one_group_calibration_converges_monotonically(self, sala_basica):
        result = calibrate_alpha(sala_basica, {"500": 0.8})
        assert set(result) == {"500", "diagnostics"}
        assert all(alpha > 0.05 for alpha in result["500"].values())

        diagnostic = result["diagnostics"]["500"]
        history = diagnostic["objective_history"]
        assert all(current >= following for current, following in zip(history, history[1:]))
        assert history[-1] < history[0]
        assert diagnostic["converged"] is True
        assert diagnostic["predicted_rt60_s"] == pytest.approx(0.8, rel=1e-4)
        assert diagnostic["identifiable_parameters"] == 1
        assert "room-wide" in diagnostic["grouping"]

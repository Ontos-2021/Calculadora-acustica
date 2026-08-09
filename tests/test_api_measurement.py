from __future__ import annotations

import math

import pytest

from acoustic_core.measurement import generate_ess, generate_wav_bytes


def test_full_ess_wav_download_is_complete(client, paid_headers):
    response = client.post(
        "/api/v1/measurement/ess/wav",
        json={
            "f1_hz": 100,
            "f2_hz": 3000,
            "duration_s": 0.05,
            "sample_rate": 8000,
            "bit_depth": 16,
        },
        headers=paid_headers,
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content[:4] == b"RIFF"
    assert response.content[8:12] == b"WAVE"
    assert len(response.content) == 44 + 400 * 2


def test_direct_deconvolution_contract_recovers_identity_peak(client, paid_headers):
    sweep = generate_ess(100, 3000, 0.05, 8000)
    response = client.post(
        "/api/v1/measurement/deconvolve",
        json={
            "response": list(sweep),
            "ess": list(sweep),
            "sample_rate": 8000,
            "f1_hz": 100,
            "f2_hz": 3000,
        },
        headers=paid_headers,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["total_samples"] == 1
    assert data["impulse_response"][0] == pytest.approx(1.0, abs=0.05)


def test_bounded_wav_import_and_ir_analysis(client, paid_headers):
    signal = [1.0] + [0.0] * 799
    wav = generate_wav_bytes(signal, 8000)
    files = {"file": ("impulse.wav", wav, "audio/wav")}

    imported = client.post(
        "/api/v1/measurement/wav/import",
        files=files,
        headers=paid_headers,
    )
    analyzed = client.post(
        "/api/v1/measurement/wav/analyze",
        files={"file": ("impulse.wav", wav, "audio/wav")},
        headers=paid_headers,
    )

    assert imported.status_code == 200, imported.text
    assert imported.json()["num_frames"] == 800
    assert imported.json()["parameters"] is None
    assert analyzed.status_code == 200, analyzed.text
    assert analyzed.json()["parameters"]["metric_context"] == "measured"
    assert analyzed.json()["parameters"]["direct_arrival_sample"] == 0


def test_corrupt_wav_is_rejected_as_input_error(client, paid_headers):
    response = client.post(
        "/api/v1/measurement/wav/import",
        files={"file": ("bad.wav", b"not a wave", "audio/wav")},
        headers=paid_headers,
    )
    assert response.status_code == 422


def test_octave_filter_and_spectrogram_endpoints(client, paid_headers):
    sample_rate = 8000
    signal = [
        math.sin(2 * math.pi * 1000 * index / sample_rate)
        for index in range(1024)
    ]
    filtered = client.post(
        "/api/v1/measurement/filter",
        json={
            "signal": signal,
            "sample_rate": sample_rate,
            "center_hz": 1000,
            "fraction": 3,
        },
        headers=paid_headers,
    )
    spectrogram = client.post(
        "/api/v1/measurement/spectrogram",
        json={
            "signal": signal,
            "sample_rate": sample_rate,
            "window_size": 256,
            "hop_size": 128,
        },
        headers=paid_headers,
    )

    assert filtered.status_code == 200, filtered.text
    assert len(filtered.json()["signal"]) == len(signal)
    assert filtered.json()["fraction"] == 3
    assert spectrogram.status_code == 200, spectrogram.text
    first_frame = spectrogram.json()["magnitude"][0]
    peak_bin = max(range(len(first_frame)), key=first_frame.__getitem__)
    assert spectrogram.json()["frequencies_hz"][peak_bin] == pytest.approx(1000)


def test_modal_q_and_calibration_diagnostics_are_exposed(client, paid_headers):
    sample_rate = 8000
    frequency = 250
    expected_q = 25
    signal = [
        math.exp(-math.pi * frequency * index / sample_rate / expected_q)
        * math.sin(2 * math.pi * frequency * index / sample_rate)
        for index in range(4000)
    ]
    modal_q = client.post(
        "/api/v1/measurement/modal-q",
        json={
            "signal": signal,
            "sample_rate": sample_rate,
            "target_frequency_hz": frequency,
        },
        headers=paid_headers,
    )
    calibration = client.post(
        "/api/v1/measurement/calibrate",
        json={
            "largo": 5,
            "ancho": 4,
            "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "measured_rt60": {"500": 0.8},
        },
        headers=paid_headers,
    )

    assert modal_q.status_code == 200, modal_q.text
    assert modal_q.json()["Q"] == pytest.approx(expected_q, rel=0.02)
    assert calibration.status_code == 200, calibration.text
    assert calibration.json()["diagnostics"]["500"]["identifiable_parameters"] == 1

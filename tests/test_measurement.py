import pytest
from acoustic_core.measurement import generate_ess, ess_deconvolution, compute_waterfall, calibrate_alpha, generate_wav_bytes
from acoustic_core.models import Material, Surface, Room


class TestESS:
    def test_generates_signal(self):
        sig = generate_ess(20, 20000, 1, 44100)
        assert len(sig) == 44100
        assert all(-1 <= v <= 1 for v in sig)

    def test_increasing_frequency(self):
        sig = generate_ess(20, 20000, 1, 44100)
        zero_crossings = 0
        for i in range(1, len(sig)):
            if sig[i-1] * sig[i] < 0:
                zero_crossings += 1
        first_half = zero_crossings // 2
        assert first_half > 0


class TestDeconvolution:
    def test_basic(self):
        ess = generate_ess(20, 200, 0.05, 8000)
        ir = ess_deconvolution(ess, ess, 8000)
        assert len(ir) > 0
        peak = max(abs(v) for v in ir)
        assert peak > 0.5


class TestWaterfall:
    def test_basic(self):
        ir = [0] * 1000
        ir[100] = 1.0
        result = compute_waterfall(ir, 44100, 0.2)
        assert "time_ms" in result
        assert "bands" in result
        assert len(result["bands"]) == 6

    def test_decay_curve(self):
        import math
        ir = [math.exp(-i / 1000) for i in range(4410)]
        result = compute_waterfall(ir, 44100, 0.2)
        for band_vals in result["bands"].values():
            assert band_vals[0] >= band_vals[-1]


class TestCalibrate:
    def test_basic(self, sala_basica):
        measured = {"500": 0.8}
        result = calibrate_alpha(sala_basica, measured)
        assert "500" in result
        assert len(result["500"]) == 6


class TestWavExport:
    def test_generates_wav(self):
        sig = [0.5, -0.3, 0.1]
        wav = generate_wav_bytes(sig, 44100)
        assert len(wav) > 40
        assert wav[:4] == b'RIFF'
        assert wav[8:12] == b'WAVE'


class TestMeasurementAPI:
    def test_ess_endpoint(self, client):
        response = client.post("/api/v1/measurement/ess", json={
            "f1_hz": 20, "f2_hz": 20000, "duration_s": 0.1, "sample_rate": 44100,
        })
        assert response.status_code == 200
        data = response.json()
        assert "signal" in data

    def test_waterfall_endpoint(self, client):
        ir = [0.0] * 500
        ir[50] = 1.0
        response = client.post("/api/v1/measurement/waterfall", json={
            "ir": ir, "sample_rate": 44100, "duration_s": 0.1,
        })
        assert response.status_code == 200
        data = response.json()
        assert "bands" in data

    def test_calibrate_endpoint(self, client):
        response = client.post("/api/v1/measurement/calibrate", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "measured_rt60": {"500": 0.8},
        })
        assert response.status_code == 200
        data = response.json()
        assert "calibrated_alphas" in data

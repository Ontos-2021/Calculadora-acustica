from acoustic_core.impulse import (
    schroeder_integration, _linear_regression_db,
    calculate_iso3382_parameters,
)


class TestSchroederIntegration:
    def test_synthetic_decay(self):
        # IR que decae exponencialmente
        import math
        fs = 44100
        ir = [math.exp(-i / fs * 10) for i in range(fs)]
        decay = schroeder_integration(ir, fs)
        assert len(decay) == len(ir)
        # El decaimiento debe empezar en 0 dB
        assert abs(decay[0]) < 0.1 or decay[0] <= 0

    def test_empty_ir(self):
        decay = schroeder_integration([], 44100)
        assert decay == []


class TestLinearRegression:
    def test_perfect_decay(self):
        # Señal que decae linealmente en dB
        fs = 44100
        decay = [0.0] * fs
        for i in range(fs):
            decay[i] = -i / fs * 60  # 0 a -60 dB
        rt60 = _linear_regression_db(decay, fs, -5, -35)
        assert 0.8 < rt60 < 1.2  # debería ser ~1.0s

    def test_no_decay(self):
        decay = [0.0] * 1000
        rt60 = _linear_regression_db(decay, 44100, -5, -35)
        assert rt60 == 0.0

    def test_few_points(self):
        decay = [-1.0, -2.0, -3.0]
        rt60 = _linear_regression_db(decay, 44100, -5, -35)
        assert rt60 == 0.0


class TestISO3382:
    def test_zero_ir(self):
        params = calculate_iso3382_parameters([0.0] * 100, 44100)
        assert "error" in params

    def test_direct_only(self):
        # IR con solo un pico directo
        ir = [0.0] * 44100
        ir[0] = 1.0
        params = calculate_iso3382_parameters(ir, 44100, 0)
        # C80 debe ser alto (toda la energía es temprana)
        assert params["C80"] > 0

    def test_energy_conservation(self):
        import math
        fs = 44100
        ir = [math.exp(-i / fs * 8) for i in range(fs // 2)]
        params = calculate_iso3382_parameters(ir, fs, 0)
        assert params["T20"] > 0
        assert params["T30"] > 0

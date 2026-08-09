import math
import random

import pytest

from acoustic_core.impulse import (
    schroeder_integration, _linear_regression_db,
    calculate_iso3382_parameters, detect_flutter_echo,
    normalized_autocorrelation,
)


class TestSchroederIntegration:
    def test_synthetic_decay(self):
        # IR que decae exponencialmente
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
        fs = 44100
        ir = [math.exp(-i / fs * 8) for i in range(fs // 2)]
        params = calculate_iso3382_parameters(ir, fs, 0)
        assert params["T20"] > 0
        assert params["T30"] > 0

    def test_iso_decay_ranges_recover_analytic_rt(self):
        fs = 8000
        expected_rt = 1.2
        pressure_rate = math.log(1000.0) / expected_rt
        ir = [math.exp(-pressure_rate * index / fs) for index in range(2 * fs)]
        params = calculate_iso3382_parameters(ir, fs)

        assert params["EDT"] == pytest.approx(expected_rt, rel=2e-4)
        assert params["T20"] == pytest.approx(expected_rt, rel=2e-4)
        assert params["T30"] == pytest.approx(expected_rt, rel=2e-4)
        assert params["regression_diagnostics"]["EDT"]["range_db"] == [0.0, -10.0]
        assert params["regression_diagnostics"]["T20"]["range_db"] == [-5.0, -25.0]
        assert params["regression_diagnostics"]["T30"]["range_db"] == [-5.0, -35.0]
        assert params["regression_diagnostics"]["T30"]["slope_db_per_s"] == pytest.approx(-50.0)
        assert params["regression_diagnostics"]["T30"]["r2"] > 0.999999
        assert params["regression_diagnostics"]["T30"]["nonlinearity_percent"] < 0.01
        assert params["metric_context"] == "predicted_model"

    def test_energy_windows_and_itdg_align_to_direct_arrival(self):
        fs = 8000
        direct = 400
        ir = [0.0] * 1600
        ir[direct] = 1.0
        ir[direct + 80] = -0.5
        ir[direct + 800] = 0.25
        params = calculate_iso3382_parameters(ir, fs, direct / fs * 1000)

        assert params["direct_arrival_sample"] == direct
        assert params["ITDG"] == pytest.approx(10.0)
        assert params["D50"] == pytest.approx(100 * 1.25 / 1.3125)
        assert params["Ts"] == pytest.approx(
            (0.010 * 0.25 + 0.100 * 0.0625) / 1.3125 * 1000
        )

    def test_direct_only_has_no_valid_decay_regression(self):
        ir = [1.0] + [0.0] * 999
        params = calculate_iso3382_parameters(ir, 8000)
        assert params["EDT"] is None
        assert params["valid_dynamic_range_db"] == 0.0
        assert params["regression_diagnostics"]["EDT"]["valid"] is False


class TestFlutterEcho:
    @staticmethod
    def _echo_train(alternating=False):
        signal = [0.0] * 4000
        for index in range(20):
            sign = -1 if alternating and index % 2 else 1
            signal[100 + index * 80] = sign * 0.9 ** index
        return signal

    def test_positive_periodic_train(self):
        result = detect_flutter_echo(self._echo_train(), 8000, start_sample=90)
        assert result["detected"] is True
        assert result["frequency"] == pytest.approx(100.0)
        assert result["correlation"] > result["threshold"]
        assert result["polarity"] == "positive"

    def test_alternating_polarity_train(self):
        result = detect_flutter_echo(
            self._echo_train(alternating=True), 8000, start_sample=90,
        )
        assert result["detected"] is True
        assert result["frequency"] == pytest.approx(100.0)
        assert result["polarity"] == "alternating"

    def test_deterministic_noise_is_not_flutter(self):
        generator = random.Random(20260808)
        noise = [generator.uniform(-1.0, 1.0) for _ in range(4000)]
        result = detect_flutter_echo(noise, 8000)
        assert result["detected"] is False

    def test_normalized_autocorrelation_zero_lag(self):
        correlation = normalized_autocorrelation([1.0, -1.0, 1.0, -1.0], 2)
        assert correlation[0] == pytest.approx(1.0)
        assert all(-1.0 <= value <= 1.0 for value in correlation)

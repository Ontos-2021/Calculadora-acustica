from acoustic_core.evaluation import (
    calculate_schroeder, calculate_modal_bandwidth,
    evaluate_bonello, find_degenerate_dimensions, get_mode_distribution,
)
from acoustic_core.models import Mode, ModeType
from acoustic_core.resonance import calculate_modes, detect_degenerate_modes, detect_overlapping_modes


class TestSchroeder:
    def test_calculo(self):
        f = calculate_schroeder(0.5, 60)
        assert f > 50
        assert f < 300

    def test_volumen_cero(self):
        assert calculate_schroeder(0.5, 0) == 0.0

    def test_rt60_cero(self):
        assert calculate_schroeder(0, 60) == 0.0


class TestModalBandwidth:
    def test_calculo(self):
        df = calculate_modal_bandwidth(0.5)
        assert df > 0

    def test_rt60_cero(self):
        assert calculate_modal_bandwidth(0) == 0.0


class TestBonello:
    def test_evaluacion(self, sala_basica):
        modos = calculate_modes(sala_basica)
        frecuencias = [m.frecuencia for m in modos]
        result = evaluate_bonello(frecuencias)
        assert "cumple" in result
        assert "bandas" in result
        assert "violaciones" in result
        assert isinstance(result["cumple"], bool)

    def test_sala_cubica_no_cumple(self, sala_cubica):
        modos = calculate_modes(sala_cubica)
        frecuencias = [m.frecuencia for m in modos]
        result = evaluate_bonello(frecuencias)
        assert not result["cumple"]

    def test_bandas_tipos(self, sala_basica):
        modos = calculate_modes(sala_basica)
        frecuencias = [m.frecuencia for m in modos]
        result = evaluate_bonello(frecuencias)
        for banda, cantidad in result["bandas"].items():
            assert isinstance(banda, float)
            assert isinstance(cantidad, int)


class TestDegenerateDimensions:
    def test_dimensiones_iguales(self):
        advertencias = find_degenerate_dimensions(3, 3, 4)
        assert len(advertencias) > 0
        assert any("iguales" in a for a in advertencias)

    def test_sin_advertencias(self):
        advertencias = find_degenerate_dimensions(5, 4, 3)
        iguales_o_multiplos = [a for a in advertencias if "iguales" in a or "múltiplo" in a]
        assert len(iguales_o_multiplos) == 0


class TestModeDistribution:
    def test_distribucion(self, sala_basica):
        modos = calculate_modes(sala_basica)
        dist = get_mode_distribution(modos)
        assert dist["axiales"] > 0
        assert dist["tangenciales"] > 0
        assert dist["oblicuos"] > 0
        total = dist["axiales"] + dist["tangenciales"] + dist["oblicuos"]
        assert total == len(modos)

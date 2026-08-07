from acoustic_core.resonance import (
    calculate_modes, classify_mode, detect_degenerate_modes, detect_overlapping_modes,
)
from acoustic_core.models import ModeType, Mode


class TestClassifyMode:
    def test_axial(self):
        tipo, peso = classify_mode(2, 0, 0)
        assert tipo == ModeType.AXIAL
        assert peso == 0.0

    def test_tangencial(self):
        tipo, peso = classify_mode(1, 1, 0)
        assert tipo == ModeType.TANGENTIAL
        assert peso == -3.0

    def test_oblicuo(self):
        tipo, peso = classify_mode(1, 1, 1)
        assert tipo == ModeType.OBLIQUE
        assert peso == -6.0

    def test_cero(self):
        tipo, peso = classify_mode(0, 0, 0)
        assert tipo == ModeType.OBLIQUE


class TestCalculateModes:
    def test_cantidad_modos(self, sala_basica):
        modos = calculate_modes(sala_basica)
        assert len(modos) == 124

    def test_primer_modo_frecuencia(self, sala_basica):
        modos = calculate_modes(sala_basica)
        assert modos[0].frecuencia > 0

    def test_ordenados(self, sala_basica):
        modos = calculate_modes(sala_basica)
        for i in range(len(modos) - 1):
            assert modos[i].frecuencia <= modos[i + 1].frecuencia

    def test_clasificacion(self, sala_basica):
        modos = calculate_modes(sala_basica)
        tipos = {m.tipo for m in modos}
        assert ModeType.AXIAL in tipos
        assert ModeType.TANGENTIAL in tipos
        assert ModeType.OBLIQUE in tipos

    def test_sin_cero(self, sala_basica):
        modos = calculate_modes(sala_basica)
        for m in modos:
            assert m.indices != [0, 0, 0]


class TestDegenerate:
    def test_sala_cubica_degenerada(self, sala_cubica):
        modos = calculate_modes(sala_cubica)
        modos = detect_degenerate_modes(modos)
        degenerados = sum(1 for m in modos if m.degenerado)
        assert degenerados > 50

    def test_sala_no_degenerada(self, sala_basica):
        modos = calculate_modes(sala_basica)
        modos = detect_degenerate_modes(modos)
        degenerados = sum(1 for m in modos if m.degenerado)
        assert degenerados < len(modos)


class TestOverlapping:
    def test_solapamiento_pequeno(self, sala_basica):
        modos = calculate_modes(sala_basica)
        modos = detect_overlapping_modes(modos, 5.0)
        solapados = sum(1 for m in modos if m.solapado)
        assert solapados >= 0

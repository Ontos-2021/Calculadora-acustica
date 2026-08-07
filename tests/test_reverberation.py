from acoustic_core.reverberation import (
    calculate_rt60, rt60_sabine, rt60_eyring, rt60_millington, rt60_fitzroy,
    rt60_promedio_sabine,
)


class TestRT60PorBanda:
    def test_calcula_todas_las_bandas(self, sala_basica):
        result = calculate_rt60(sala_basica)
        assert set(result.keys()) == {"125", "250", "500", "1000", "2000", "4000"}

    def test_calcula_todos_los_metodos(self, sala_basica):
        result = calculate_rt60(sala_basica)
        for banda in result:
            assert set(result[banda].keys()) == {"Sabine", "Eyring", "Millington", "FitzRoy"}

    def test_valores_positivos(self, sala_basica):
        result = calculate_rt60(sala_basica)
        for banda in result:
            for metodo, valor in result[banda].items():
                assert valor > 0, f"{metodo} en {banda} Hz es {valor}"

    def test_convergencia_con_alfa_unico(self, sala_basica):
        result = calculate_rt60(sala_basica)
        vals_125 = list(result["125"].values())
        vals_500 = list(result["500"].values())
        # Promedio debería ser similar entre bandas si α es constante
        assert abs(sum(vals_125) / 4 - sum(vals_500) / 4) < 0.1


class TestFormulasIndividuales:
    def test_sabine(self, sala_basica):
        assert rt60_sabine(sala_basica, "500") > 0

    def test_eyring(self, sala_basica):
        assert rt60_eyring(sala_basica, "500") > 0

    def test_millington(self, sala_basica):
        assert rt60_millington(sala_basica, "500") > 0

    def test_fitzroy(self, sala_basica):
        assert rt60_fitzroy(sala_basica, "500") > 0

    def test_sabine_menor_que_infinito(self, sala_basica):
        assert rt60_sabine(sala_basica, "500") < 100


class TestPromedio:
    def test_promedio(self, sala_basica):
        prom = rt60_promedio_sabine(sala_basica)
        assert prom > 0

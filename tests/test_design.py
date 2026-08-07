from acoustic_core.design import find_closest_ratio, get_rt60_target


class TestProporciones:
    def test_encuentra_cercana(self):
        result = find_closest_ratio(5, 4, 3)
        assert "mas_cercana" in result
        assert result["mas_cercana"] is not None
        assert "error" in result

    def test_proporcion_actual_ordenada(self):
        result = find_closest_ratio(8, 5, 3)
        prop = result["proporcion_actual"]
        assert prop[0] == 1
        assert prop[1] >= 1
        assert prop[2] >= prop[1]

    def test_todas_listadas(self):
        result = find_closest_ratio(5, 4, 3)
        assert len(result["todas"]) == 5


class TestRT60Objetivo:
    def test_uso_valido(self):
        target = get_rt60_target("home_studio")
        assert target is not None
        assert "label" in target
        assert "valores" in target
        assert "500" in target["valores"]

    def test_uso_invalido(self):
        assert get_rt60_target("uso_inexistente") is None

    def test_todos_los_usos_tienen_6_bandas(self):
        from acoustic_core.design import RT60_OBJETIVOS
        for uso, data in RT60_OBJETIVOS.items():
            assert len(data["valores"]) == 6

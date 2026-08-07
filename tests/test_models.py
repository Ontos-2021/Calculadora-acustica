import pytest
from acoustic_core.models import Material, Room, BANDAS_OCTAVA


class TestMaterial:
    def test_alpha_unico(self):
        m = Material(nombre="Test", alpha_unico=0.3)
        for b in BANDAS_OCTAVA:
            assert m.alpha[b] == 0.3

    def test_alpha_por_banda(self):
        m = Material(nombre="Test", alphas={"125": 0.1, "500": 0.5})
        assert m.alpha["125"] == 0.1
        assert m.alpha["500"] == 0.5

    def test_alpha_unico_prioritario(self):
        m = Material(nombre="Test", alpha_unico=0.2, alphas={"125": 0.9})
        assert m.alpha["125"] == 0.2
        assert m.alpha["500"] == 0.2

    def test_alpha_fuera_rango(self):
        with pytest.raises(ValueError):
            Material(nombre="Test", alpha_unico=1.5)

    def test_sin_alphas(self):
        with pytest.raises(ValueError):
            Material(nombre="Test")

    def test_banda_invalida(self):
        with pytest.raises(ValueError):
            Material(nombre="Test", alphas={"9999": 0.5})

    def test_presets_cargados(self):
        from acoustic_core.presets import MATERIALES_PRESETS
        assert len(MATERIALES_PRESETS) >= 5
        for nombre, mat in MATERIALES_PRESETS.items():
            assert len(mat.alpha) == 6


class TestRoom:
    def test_volumen(self, sala_basica):
        assert sala_basica.volumen == 60.0

    def test_superficie_total(self, sala_basica):
        assert sala_basica.superficie_total == 94.0

    def test_dimension_invalida(self):
        from acoustic_core.models import Surface, Room
        with pytest.raises(ValueError):
            Room(largo=-1, ancho=4, alto=3, superficies=[
                Surface(nombre="F", area=1, material=Material(nombre="X", alpha_unico=0.1))
                for _ in range(6)
            ])

    def test_menos_de_6_superficies(self):
        from acoustic_core.models import Surface, Room
        with pytest.raises(ValueError):
            Room(largo=5, ancho=4, alto=3, superficies=[])

    def test_uso_opcional(self, sala_basica):
        assert sala_basica.uso is None
        r = Room(
            largo=5, ancho=4, alto=3,
            superficies=sala_basica.superficies,
            uso="home_studio",
        )
        assert r.uso == "home_studio"

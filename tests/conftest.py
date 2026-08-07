import pytest
from acoustic_core.models import Material, Surface, Room
from acoustic_core.presets import MATERIALES_PRESETS


@pytest.fixture
def mat_concreto():
    return Material(nombre="Concreto", alpha_unico=0.05)


@pytest.fixture
def mat_panel():
    return Material(
        nombre="Panel acústico",
        alphas={"125": 0.20, "250": 0.60, "500": 0.85, "1000": 0.90, "2000": 0.85, "4000": 0.80},
    )


@pytest.fixture
def sala_basica(mat_concreto):
    return Room(
        largo=5.0, ancho=4.0, alto=3.0,
        superficies=[Surface(nombre=n, area=a, material=mat_concreto)
                     for n, a in zip(
            ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"],
            [12.0, 12.0, 15.0, 15.0, 20.0, 20.0],
        )],
    )


@pytest.fixture
def sala_cubica(mat_concreto):
    return Room(
        largo=3.0, ancho=3.0, alto=3.0,
        superficies=[Surface(nombre=n, area=9.0, material=mat_concreto)
                     for n in ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"]],
    )


@pytest.fixture
def app():
    from app import create_app
    app = create_app()
    return app


@pytest.fixture
def client(app):
    return app.test_client()

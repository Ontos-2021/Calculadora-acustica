from acoustic_core.models import Room, Surface, Material
from acoustic_core.pressure import (
    compute_pressure_map, compute_single_mode_grid,
    find_optimal_listening,
)

m = Material(nombre="C", alpha_unico=0.1)
sup = [Surface(nombre=n, area=a, material=m) for n, a in zip(
    ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"],
    [12, 12, 15, 15, 20, 20])]


def _sala(largo=5, ancho=4, alto=3):
    return Room(largo=largo, ancho=ancho, alto=alto, superficies=sup)


class TestPressureMap:
    def test_grid_size(self):
        r = _sala()
        pm = compute_pressure_map(r, grid_size=50)
        assert len(pm["grid_x"]) == 50
        assert len(pm["grid_y"]) == 50
        assert len(pm["pressure"]) == 50
        assert len(pm["pressure"][0]) == 50

    def test_values_normalized(self):
        r = _sala()
        pm = compute_pressure_map(r, max_freq=200)
        flat = [v for row in pm["pressure"] for v in row]
        assert max(flat) <= 1.0
        assert min(flat) >= 0.0

    def test_corner_max(self):
        r = _sala()
        # Para modo axial (1,0,0), la presión es máxima en x=0 y x=L
        for modo in [None]:
            pm = compute_pressure_map(r, max_freq=100)
        # Esquina (0,0) debe tener alta presión para modo axial
        assert pm["pressure"][0][0] > 0.5

    def test_single_mode(self):
        r = _sala()
        sm = compute_single_mode_grid(r, 1, 0, 0, grid_size=10)
        assert len(sm["grid_x"]) == 10
        assert "pressure" in sm


class TestOptimalListening:
    def test_returns_position(self):
        r = _sala()
        opt = find_optimal_listening(r, grid_size=20)
        assert "x" in opt
        assert "y" in opt
        assert "score" in opt
        assert 0 <= opt["x"] <= 5
        assert 0 <= opt["y"] <= 4
        assert opt["score"] >= 0

    def test_sala_cubica(self):
        r = _sala(3, 3, 3)
        opt = find_optimal_listening(r, grid_size=20)
        assert opt["score"] > 0

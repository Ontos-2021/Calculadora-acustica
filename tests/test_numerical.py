import pytest
from acoustic_core.finite_impedance import axial_modes_finite_impedance, room_modes_finite_impedance
from acoustic_core.fem2d import compute_2d_modes


class TestFiniteImpedance:
    def test_axial_modes_basic(self):
        modes = axial_modes_finite_impedance(5, 10000, max_modes=3)
        assert len(modes) == 3
        assert all(m["frequency_hz"] > 0 for m in modes)

    def test_damping_present(self):
        modes = axial_modes_finite_impedance(5, 1000, max_modes=3)
        assert modes[0]["damping_neper_s"] != 0

    def test_higher_damping_lower_impedance(self):
        low_z = axial_modes_finite_impedance(5, 500, max_modes=1)
        high_z = axial_modes_finite_impedance(5, 10000, max_modes=1)
        assert low_z[0]["damping_neper_s"] < 0
        assert abs(low_z[0]["damping_neper_s"]) > abs(high_z[0]["damping_neper_s"])

    def test_room_modes(self):
        modes = room_modes_finite_impedance(5, 4, 3, 10000, max_order=2)
        assert len(modes) >= 4
        assert all(m["rigid_frequency_hz"] > 0 for m in modes)


class TestFEM2D:
    def test_rectangular_modes(self):
        modes = compute_2d_modes(5, 4, grid_nx=15, grid_ny=15, num_modes=3)
        assert len(modes) >= 1
        assert all(m["frequency_hz"] > 0 for m in modes)

    def test_mode_shape(self):
        modes = compute_2d_modes(5, 4, grid_nx=10, grid_ny=10, num_modes=1)
        if modes:
            assert "shape_2d" in modes[0]
            assert len(modes[0]["shape_2d"]) == 10


class TestNumericalAPI:
    def test_finite_impedance(self, client):
        response = client.post("/api/v1/numerical/finite-impedance", json={
            "L_m": 5, "Z_wall": 10000, "max_order": 3,
        })
        assert response.status_code == 200
        data = response.json()
        assert "axial_modes" in data

    def test_fem2d(self, client):
        response = client.post("/api/v1/numerical/fem2d", json={
            "width": 5, "height": 4, "grid_nx": 10, "grid_ny": 10, "num_modes": 2,
        })
        assert response.status_code == 200
        data = response.json()
        assert "modes" in data

    def test_ray_tracing(self, client):
        response = client.post("/api/v1/numerical/ray-tracing", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "num_rays": 50, "max_reflections": 10,
        })
        assert response.status_code == 200
        data = response.json()
        assert "energy_db" in data

    def test_hybrid(self, client):
        response = client.post("/api/v1/numerical/hybrid", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
            "num_rays": 50,
        })
        assert response.status_code == 200
        data = response.json()
        assert "hybrid" in data

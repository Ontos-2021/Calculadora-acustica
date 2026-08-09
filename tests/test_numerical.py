import math

import numpy as np
import pytest
from scipy.sparse import issparse

from acoustic_core.fem2d import compute_2d_modes
from acoustic_core.finite_impedance import axial_modes_finite_impedance, room_modes_finite_impedance
from acoustic_numerics.fem2d import (
    assemble_matrices,
    couple_vertical_modes,
    polygon_mesh,
    rectangle_mesh,
    solve_fem_modes,
)
from acoustic_numerics.finite_impedance import (
    RootConvergenceError,
    axial_characteristic,
    solve_axial_mode,
    solve_axial_modes,
)
from acoustic_numerics.hybrid import (
    FrequencyResponse,
    choose_low_frequency_method,
    complementary_crossover_weights,
    hybridize_frequency_responses,
)
from acoustic_numerics.ray_tracing import (
    AcousticScene,
    BandMaterial,
    PlaneSurface,
    RayTraceConfig,
    TriangleSurface,
    segment_sphere_intersection,
    shoebox_scene,
    trace_scene,
)


class TestFiniteImpedance:
    def test_rigid_limit_matches_analytic_modes(self):
        modes = solve_axial_modes(5.0, math.inf, num_modes=3)
        assert [mode.frequency_real_hz for mode in modes] == pytest.approx([34.3, 68.6, 102.9])
        assert all(mode.decay_rate_neper_s == 0.0 for mode in modes)
        assert all(mode.residual == 0.0 for mode in modes)

    def test_complex_frequency_dependent_impedance_and_residual(self):
        impedance = lambda frequency_hz: 8000.0 + 2j * frequency_hz
        mode = solve_axial_mode(5.0, impedance, 1)
        residual = axial_characteristic(mode.wavenumber_per_m, 5.0, impedance)
        assert mode.converged
        assert mode.frequency_hz.imag < 0.0
        assert abs(residual) < 1e-9
        assert mode.residual < 1e-9

    def test_decay_units_and_rt60_conversion(self):
        low_impedance = solve_axial_mode(5.0, 500.0, 1)
        high_impedance = solve_axial_mode(5.0, 10000.0, 1)
        assert low_impedance.decay_rate_neper_s > high_impedance.decay_rate_neper_s > 0.0
        assert low_impedance.rt60_s * low_impedance.decay_rate_neper_s == pytest.approx(
            3.0 * math.log(10.0)
        )
        assert low_impedance.decay_rate_neper_s == pytest.approx(
            -2.0 * math.pi * low_impedance.frequency_hz.imag
        )

    def test_perfectly_matched_termination_has_no_discrete_pole(self):
        with pytest.raises(RootConvergenceError, match="perfectly matched"):
            solve_axial_mode(5.0, 1.2 * 343.0, 1)

    def test_low_impedance_branches_are_unique_and_approach_pressure_release(self):
        modes = solve_axial_modes(5.0, 100.0, num_modes=4)
        frequencies = [mode.frequency_real_hz for mode in modes]
        assert frequencies == sorted(set(frequencies))
        assert frequencies == pytest.approx([17.15, 51.45, 85.75, 120.05])

    def test_legacy_adapter_reports_positive_decay_and_residual(self):
        modes = axial_modes_finite_impedance(5.0, 1000.0, max_modes=3)
        assert len(modes) == 3
        assert all(mode["frequency_hz"] > 0.0 for mode in modes)
        assert all(mode["damping_neper_s"] > 0.0 for mode in modes)
        assert all(mode["residual"] < 1e-9 for mode in modes)

    def test_room_modes_preserve_legacy_contract(self):
        modes = room_modes_finite_impedance(5.0, 4.0, 3.0, 10000.0, max_order=2)
        assert len(modes) >= 4
        assert all(mode["rigid_frequency_hz"] > 0.0 for mode in modes)
        assert all(mode["damping_neper_s"] >= 0.0 for mode in modes)
        assert all("active-axis" in mode["model"] for mode in modes)


class TestFEM2D:
    def test_sparse_generalized_eigenproblem_and_mode_shape(self):
        mesh = rectangle_mesh(5.0, 4.0, nx=11, ny=9)
        stiffness, mass = assemble_matrices(mesh)
        result = solve_fem_modes(mesh, num_modes=3)
        assert issparse(stiffness) and issparse(mass)
        assert "finite element" in result.method
        assert len(result.modes) == 3
        assert all(mode.frequency_hz > 0.0 for mode in result.modes)
        assert all(mode.shape.shape == (len(mesh.nodes),) for mode in result.modes)
        assert all(mode.residual < 1e-8 for mode in result.modes)

    @pytest.mark.parametrize(
        "vertices",
        [
            [(0, 0), (5, 0), (5, 2), (3, 2), (3, 4), (0, 4)],
            [(0, 0), (5, 0), (4, 3), (0, 3)],
        ],
        ids=["l_shape", "trapezoid"],
    )
    def test_polygonal_geometry(self, vertices):
        mesh = polygon_mesh(vertices, target_edge_length_m=0.6)
        result = solve_fem_modes(mesh, num_modes=2)
        assert len(mesh.elements) > 10
        assert len(result.modes) == 2
        assert result.modes[0].frequency_hz < result.modes[1].frequency_hz

    def test_impedance_boundary_hook_produces_damped_modes(self):
        mesh = rectangle_mesh(2.0, 1.5, nx=6, ny=5)
        result = solve_fem_modes(mesh, num_modes=1, boundary_impedance=10000.0)
        mode = result.modes[0]
        assert mode.complex_frequency_hz.imag < 0.0
        assert mode.decay_rate_neper_s > 0.0
        assert mode.residual < 1e-7
        assert "quadratic" in result.boundary_condition

    def test_vertical_analytic_coupling(self):
        horizontal = solve_fem_modes(rectangle_mesh(5.0, 4.0, 8, 7), num_modes=1).modes
        coupled = couple_vertical_modes(horizontal, height_m=3.0, max_vertical_order=1)
        assert len(coupled) == 2
        horizontal_only = next(mode for mode in coupled if mode.vertical_order == 0)
        vertical_coupled = next(mode for mode in coupled if mode.vertical_order == 1)
        assert horizontal_only.frequency_hz == pytest.approx(horizontal[0].frequency_hz)
        assert vertical_coupled.frequency_hz > horizontal_only.frequency_hz

    def test_legacy_grid_shape(self):
        modes = compute_2d_modes(5.0, 4.0, grid_nx=10, grid_ny=9, num_modes=1)
        assert len(modes) == 1
        assert len(modes[0]["shape_2d"]) == 9
        assert len(modes[0]["shape_2d"][0]) == 10
        assert "finite element" in modes[0]["method"]


class TestRayTracing:
    def test_complete_segment_listener_intersection(self):
        distance = segment_sphere_intersection((0, 0, 0), (10, 0, 0), (5, 0.5, 0), 1.0)
        assert distance == pytest.approx(5.0 - math.sqrt(0.75))
        assert segment_sphere_intersection((0, 0, 0), (4, 0, 0), (5, 0, 0), 0.5) is None

    def test_triangle_and_plane_geometry_contract(self):
        triangle = TriangleSurface(
            ((2, -1, -1), (2, 1, -1), (2, 0, 1)),
            "triangle",
            BandMaterial(absorption=0.2),
        )
        plane = PlaneSurface((4, 0, 0), (-1, 0, 0), "plane")
        scene = AcousticScene(triangles=[triangle], planes=[plane])
        hit = scene.intersect((0, 0, 0), (1, 0, 0))
        assert hit is not None
        assert hit.surface_id == "triangle"
        assert hit.distance_m == pytest.approx(2.0)
        assert scene.bvh.split_strategy == "binned SAH"

    def test_seeded_band_transport_is_deterministic(self):
        scene = shoebox_scene((5, 4, 3), BandMaterial(absorption={125: 0.1, 1000: 0.4}, scattering=0.1))
        config = RayTraceConfig(
            bands_hz=(125.0, 1000.0),
            num_rays=80,
            max_reflections=5,
            max_time_s=0.2,
            seed=17,
        )
        first = trace_scene(scene, (1, 1, 1), (4, 3, 1.2), config)
        second = trace_scene(scene, (1, 1, 1), (4, 3, 1.2), config)
        np.testing.assert_array_equal(first.energy_by_band, second.energy_by_band)
        assert first.direct_time_s == pytest.approx(math.dist((1, 1, 1), (4, 3, 1.2)) / 343.0)
        assert sum(stat.hit_count for stat in first.surface_statistics.values()) > 0
        assert first.total_ray_segments > 0


class TestHybrid:
    def test_solver_selection_and_complementary_weights(self):
        frequencies = np.geomspace(80.0, 800.0, 101)
        low, high = complementary_crossover_weights(frequencies, 250.0, crossover_octaves=1.0)
        np.testing.assert_allclose(low + high, 1.0, atol=1e-15)
        assert choose_low_frequency_method("shoebox") == "ism"
        assert choose_low_frequency_method("L-shape") == "fem"

    def test_frequency_resolved_hybrid_selects_fem_for_arbitrary_geometry(self):
        frequencies = (100.0, 200.0, 400.0, 800.0)
        fem = FrequencyResponse(frequencies, (1.0, 1.2, 1.1, 0.9), "fem")
        rays = FrequencyResponse(frequencies, (0.6, 0.8, 1.0, 1.1), "ray_tracing")
        result = hybridize_frequency_responses(
            high_frequency_response=rays,
            schroeder_hz=300.0,
            geometry="polygonal",
            fem_response=fem,
        )
        assert result.low_method == "fem"
        assert result.combined_values.shape == (4,)
        np.testing.assert_allclose(result.low_weights + result.high_weights, 1.0)


class TestNumericalAPI:
    def test_finite_impedance(self, client, paid_headers):
        response = client.post(
            "/api/v1/numerical/finite-impedance",
            json={"L_m": 5, "Z_wall": 10000, "max_order": 3},
            headers=paid_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["axial_modes"][0]["residual"] < 1e-9

    def test_fem2d(self, client, paid_headers):
        response = client.post(
            "/api/v1/numerical/fem2d",
            json={"width": 5, "height": 4, "grid_nx": 10, "grid_ny": 10, "num_modes": 2},
            headers=paid_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "finite element" in data["modes"][0]["method"]

    def test_ray_tracing(self, client, paid_headers):
        response = client.post(
            "/api/v1/numerical/ray-tracing",
            json={
                "largo": 5,
                "ancho": 4,
                "alto": 3,
                "superficies": [{"material": "Concreto"}] * 6,
                "num_rays": 50,
                "max_reflections": 10,
            },
            headers=paid_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "energy_by_band" in data
        assert data["seed"] == 0

    def test_hybrid(self, client, paid_headers):
        response = client.post(
            "/api/v1/numerical/hybrid",
            json={
                "largo": 5,
                "ancho": 4,
                "alto": 3,
                "superficies": [{"material": "Concreto"}] * 6,
                "num_rays": 50,
            },
            headers=paid_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "frequency_response" in data
        weights = data["frequency_response"]
        np.testing.assert_allclose(
            np.asarray(weights["low_weights"]) + np.asarray(weights["high_weights"]),
            1.0,
        )

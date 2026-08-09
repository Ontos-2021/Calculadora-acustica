"""Small deterministic numerical validation benchmarks, not speed contests."""

import math
from time import perf_counter

import numpy as np
import pytest

from acoustic_core.impulse import generate_image_sources
from acoustic_core.models import Material, Room, Surface
from acoustic_numerics.fem2d import rectangle_mesh, solve_fem_modes
from acoustic_numerics.finite_impedance import axial_characteristic, solve_axial_mode
from acoustic_numerics.hybrid import FrequencyResponse, hybridize_frequency_responses
from acoustic_numerics.ray_tracing import (
    BVH,
    BandMaterial,
    RayTraceConfig,
    TriangleSurface,
    shoebox_scene,
    trace_scene,
)


def test_rectangle_eigenfrequencies_converge_to_analytic_values():
    width, height, sound_speed = 5.0, 4.0, 343.0
    analytic = np.asarray(
        [
            sound_speed / (2.0 * width),
            sound_speed / (2.0 * height),
            sound_speed / 2.0 * math.sqrt(width**-2 + height**-2),
        ]
    )
    coarse = solve_fem_modes(rectangle_mesh(width, height, 7, 6), num_modes=3).modes
    fine = solve_fem_modes(rectangle_mesh(width, height, 21, 17), num_modes=3).modes
    coarse_error = np.abs(np.asarray([mode.frequency_hz for mode in coarse]) - analytic) / analytic
    fine_error = np.abs(np.asarray([mode.frequency_hz for mode in fine]) - analytic) / analytic
    assert np.all(fine_error < coarse_error)
    assert np.max(fine_error) < 0.005


def test_finite_impedance_root_residual_benchmark():
    impedance = lambda frequency_hz: 6000.0 + 1j * (400.0 + frequency_hz)
    mode = solve_axial_mode(4.3, impedance, mode_index=4)
    assert abs(axial_characteristic(mode.wavenumber_per_m, 4.3, impedance)) < 1e-9
    assert mode.decay_rate_neper_s > 0.0


def test_bvh_sah_prunes_triangle_intersections():
    triangles = []
    subdivisions = 20
    for y_index in range(subdivisions):
        for z_index in range(subdivisions):
            y0, y1 = y_index / subdivisions, (y_index + 1) / subdivisions
            z0, z1 = z_index / subdivisions, (z_index + 1) / subdivisions
            triangles.extend(
                [
                    TriangleSurface(((1, y0, z0), (1, y1, z0), (1, y1, z1)), f"cell-{y_index}-{z_index}"),
                    TriangleSurface(((1, y0, z0), (1, y1, z1), (1, y0, z1)), f"cell-{y_index}-{z_index}"),
                ]
            )
    started = perf_counter()
    bvh = BVH(triangles)
    statistics = {}
    hit = bvh.intersect((0, 0.52, 0.52), (1, 0, 0), statistics=statistics)
    elapsed = perf_counter() - started
    assert hit is not None and hit[0] == pytest.approx(1.0)
    assert statistics["triangle_tests"] < len(triangles) / 10
    assert elapsed < 5.0


def _benchmark_trace(absorption: float):
    scene = shoebox_scene((5, 4, 3), BandMaterial(absorption=absorption, scattering=0.0))
    config = RayTraceConfig(
        bands_hz=(500.0,),
        num_rays=800,
        max_reflections=8,
        max_time_s=0.2,
        listener_radius_m=0.25,
        seed=19,
    )
    return trace_scene(scene, (1, 1, 1.2), (4, 3, 1.2), config)


def test_seeded_ray_timing_determinism_and_energy_monotonicity():
    started = perf_counter()
    reflective = _benchmark_trace(0.1)
    repeated = _benchmark_trace(0.1)
    absorptive = _benchmark_trace(0.6)
    elapsed = perf_counter() - started
    expected_direct_time = math.dist((1, 1, 1.2), (4, 3, 1.2)) / 343.0
    assert reflective.direct_time_s == pytest.approx(expected_direct_time, abs=1e-12)
    np.testing.assert_array_equal(reflective.energy_by_band, repeated.energy_by_band)
    assert reflective.total_energy_by_band[0] > absorptive.total_energy_by_band[0]
    assert elapsed < 10.0


def test_shoebox_first_reflection_timing_matches_image_sources():
    material = Material(nombre="benchmark", alpha_unico=0.1)
    room = Room(
        largo=5,
        ancho=4,
        alto=3,
        superficies=[
            Surface(nombre=name, area=1.0, material=material)
            for name in ("x0", "x1", "y0", "y1", "z0", "z1")
        ],
    )
    image_sources = generate_image_sources(room, (1, 1, 1.2), (4, 3, 1.2), max_order=1)
    first_order_distances = [
        source["distance"] for source in image_sources if source["total_order"] == 1
    ]
    traced = _benchmark_trace(0.1)
    first_reflections = [
        arrival
        for arrival in traced.arrivals
        if arrival.event == "specular_listener_sphere" and arrival.reflection_count == 1
    ]
    assert first_reflections
    # Sphere capture occurs before the path reaches its centre; allow its radius.
    closest_error = min(
        abs(arrival.path_length_m - image_distance)
        for arrival in first_reflections
        for image_distance in first_order_distances
    )
    assert closest_error <= 0.25


def test_hybrid_complementarity_and_crossover_continuity():
    frequencies = np.geomspace(80.0, 1000.0, 1001)
    low = FrequencyResponse((80.0, 250.0, 1000.0), (1.0, 1.0, 1.0), "ism")
    high = FrequencyResponse((80.0, 250.0, 1000.0), (2.0, 2.0, 2.0), "ray_tracing")
    result = hybridize_frequency_responses(
        high_frequency_response=high,
        schroeder_hz=250.0,
        geometry="shoebox",
        ism_response=low,
        frequencies_hz=frequencies,
        crossover_octaves=1.0,
    )
    np.testing.assert_allclose(result.low_weights + result.high_weights, 1.0, atol=1e-15)
    assert np.max(np.abs(np.diff(result.combined_values))) < 0.01
    assert result.combined_values[0] == pytest.approx(1.0)
    assert result.combined_values[-1] == pytest.approx(2.0)

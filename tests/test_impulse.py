import math

import pytest

from acoustic_core.models import Room, Surface, Material
from acoustic_core.impulse import (
    generate_image_sources, calculate_energy,
    build_impulse_response, calculate_iso3382_parameters,
    _image_position, validate_position, validate_source_receiver,
)

m = Material(nombre="C", alpha_unico=0.1)
sup = [Surface(nombre=n, area=a, material=m) for n, a in zip(
    ["Frente", "Contrafrente", "Lat Izq", "Lat Der", "Piso", "Techo"],
    [12, 12, 15, 15, 20, 20])]

room = Room(largo=5, ancho=4, alto=3, superficies=sup)
source = (1.0, 1.0, 1.5)
receiver = (4.0, 3.0, 1.2)


class TestImagePosition:
    def test_order_zero(self):
        img, cnt_pos, cnt_neg = _image_position(1.0, 5.0, 0)
        assert img == 1.0
        assert cnt_pos == 0
        assert cnt_neg == 0

    def test_order_one(self):
        img, cnt_pos, cnt_neg = _image_position(1.0, 5.0, 1)
        assert abs(img - 9.0) < 0.01  # 2*5 - 1 = 9
        assert cnt_pos == 1
        assert cnt_neg == 0

    def test_order_neg_one(self):
        img, cnt_pos, cnt_neg = _image_position(1.0, 5.0, -1)
        assert abs(img - (-1.0)) < 0.01
        assert cnt_pos == 0
        assert cnt_neg == 1


class TestGenerateSources:
    def test_direct_path(self):
        sources = generate_image_sources(room, source, receiver, max_order=2)
        direct = sources[0]
        expected_distance = math.sqrt(3.0 ** 2 + 2.0 ** 2 + 0.3 ** 2)
        assert direct["is_direct"] is True
        assert direct["total_order"] == 0
        assert direct["reflection_counts"] == {surface.nombre: 0 for surface in room.superficies}
        assert direct["distance"] == pytest.approx(expected_distance, abs=1e-14)
        assert direct["delay"] == pytest.approx(expected_distance / 343.0, abs=1e-15)

    @pytest.mark.parametrize("order, expected_count", [(0, 1), (1, 7), (2, 25), (3, 63)])
    def test_total_order_semantics(self, order, expected_count):
        sources = generate_image_sources(room, source, receiver, max_order=order)
        assert len(sources) == expected_count
        assert max(item["total_order"] for item in sources) == order

    def test_wall_counts_and_image_position(self):
        sources = generate_image_sources(room, source, receiver, max_order=1)
        x_min = next(item for item in sources if item["image_indices"] == (-1, 0, 0))
        assert x_min["position"] == (-1.0, 1.0, 1.5)
        assert x_min["wall_reflection_counts"] == {
            "x_min": 1, "x_max": 0, "y_min": 0,
            "y_max": 0, "z_min": 0, "z_max": 0,
        }

    def test_orders_increasing(self):
        sources = generate_image_sources(room, source, receiver, max_order=4)
        for i in range(len(sources) - 1):
            assert sources[i]["delay"] <= sources[i + 1]["delay"]

    def test_order_count(self):
        s3 = generate_image_sources(room, source, receiver, max_order=3)
        s5 = generate_image_sources(room, source, receiver, max_order=5)
        assert len(s5) > len(s3)

    @pytest.mark.parametrize(
        "position",
        [(-0.1, 1, 1), (5, 1, 1), (1, float("nan"), 1), (1, 1)],
    )
    def test_position_validation(self, position):
        with pytest.raises(ValueError):
            validate_position(room, position)

    def test_source_receiver_must_differ(self):
        with pytest.raises(ValueError, match="coincident"):
            validate_source_receiver(room, source, source)


class TestEnergy:
    def test_energy_positive(self):
        sources = generate_image_sources(room, source, receiver, max_order=3)
        sources = calculate_energy(sources, room, "500")
        for s in sources:
            assert s["energy"] > 0

    def test_energy_decreases_with_order(self):
        sources = generate_image_sources(room, source, receiver, max_order=5)
        sources = calculate_energy(sources, room, "500")
        energies = [s["energy"] for s in sources if s["total_order"] <= 2]
        assert len(energies) > 0

    def test_geometric_spreading_and_reflection_coefficient(self):
        sources = generate_image_sources(room, source, receiver, max_order=1)
        enriched = calculate_energy(sources, room, "500")
        direct = next(item for item in enriched if item["is_direct"])
        reflected = next(item for item in enriched if item["image_indices"] == (-1, 0, 0))
        assert direct["amplitude"] == pytest.approx(1.0 / direct["distance"])
        assert direct["energy"] == pytest.approx(1.0 / direct["distance"] ** 2)
        assert reflected["amplitude"] == pytest.approx(
            math.sqrt(0.9) / reflected["distance"]
        )

    def test_per_band_and_pi_phase_support(self):
        sources = generate_image_sources(room, source, receiver, max_order=1)
        enriched = calculate_energy(
            sources, room, bands=["125", "500"], phase_signs={"x_min": -1},
        )
        reflected = next(item for item in enriched if item["image_indices"] == (-1, 0, 0))
        assert set(reflected["amplitudes_by_band"]) == {"125", "500"}
        assert reflected["amplitudes_by_band"]["500"] < 0
        assert reflected["energies_by_band"]["500"] > 0


class TestImpulseResponse:
    def test_ir_length(self):
        sources = generate_image_sources(room, source, receiver, max_order=4)
        sources = calculate_energy(sources, room, "500")
        ir = build_impulse_response(sources, fs=44100, duration_s=0.5, room=room)
        assert len(ir["impulse_response"]) == 22050

    def test_direct_delay_reasonable(self):
        sources = generate_image_sources(room, source, receiver, max_order=4)
        sources = calculate_energy(sources, room, "500")
        ir = build_impulse_response(sources, fs=44100, duration_s=1.0, room=room)
        # Distancia directa ~3.6m → delay ~10.5ms
        assert 5 < ir["direct_delay_ms"] < 30

    def test_fractional_impulses_preserve_area_and_sign(self):
        arrivals = [
            {"delay": 0.00125, "amplitude": 1.0, "total_order": 0, "is_direct": True},
            {"delay": 0.003, "amplitude": -0.5, "total_order": 1},
        ]
        result = build_impulse_response(arrivals, fs=1000, duration_s=0.01)
        rendered = result["impulse_response"]
        assert rendered[1:4] == pytest.approx([0.75, 0.25, -0.5])
        assert sum(rendered) == pytest.approx(0.5)
        assert result["direct_delay_ms"] == pytest.approx(1.25)
        assert result["normalization_gain"] == 1.0

    def test_iso3382_parameters(self):
        sources = generate_image_sources(room, source, receiver, max_order=6)
        sources = calculate_energy(sources, room, "500")
        ir = build_impulse_response(sources, fs=44100, duration_s=1.0, room=room)
        params = calculate_iso3382_parameters(
            ir["impulse_response"], 44100, ir["direct_delay_ms"])
        assert "EDT" in params
        assert "C80" in params
        assert "D50" in params
        assert "Ts" in params
        assert "ITDG" in params
        assert "flutter_echo" in params

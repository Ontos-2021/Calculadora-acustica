from acoustic_core.models import Room, Surface, Material
from acoustic_core.impulse import (
    generate_image_sources, calculate_energy,
    build_impulse_response, calculate_iso3382_parameters,
    _image_position,
)
from acoustic_core.resonance import calculate_modes

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
    def test_direct_path(self,):
        sources = generate_image_sources(room, source, receiver, max_order=2)
        assert len(sources) > 0
        # El primer source debe tener el delay más corto (path directo)
        assert sources[0]["delay"] > 0

    def test_orders_increasing(self):
        sources = generate_image_sources(room, source, receiver, max_order=4)
        for i in range(len(sources) - 1):
            assert sources[i]["delay"] <= sources[i + 1]["delay"]

    def test_order_count(self):
        s3 = generate_image_sources(room, source, receiver, max_order=3)
        s5 = generate_image_sources(room, source, receiver, max_order=5)
        assert len(s5) > len(s3)


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

import unittest
from app.utils.calculations import calculate_resonance_modes, calculate_rt60

class TestCalculations(unittest.TestCase):

    def test_calculate_resonance_modes(self):
        largo, ancho, alto = 5, 4, 3
        result = calculate_resonance_modes(largo, ancho, alto)
        self.assertIn('modos', result)
        self.assertIn('frequencies', result)

    def test_calculate_rt60(self):
        largo, ancho, alto = 5, 4, 3
        alfas = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        result = calculate_rt60(largo, ancho, alto, alfas)
        self.assertIn('Sabine', result)
        self.assertIn('Eyring', result)
        self.assertIn('Millington', result)
        self.assertIn('Fitz Roy', result)

if __name__ == '__main__':
    unittest.main()

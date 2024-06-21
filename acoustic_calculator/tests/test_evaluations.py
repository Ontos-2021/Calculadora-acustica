import unittest
from app.utils.evaluations import criterio_de_bonello

class TestEvaluations(unittest.TestCase):

    def test_criterio_de_bonello(self):
        frecuencias = [100, 150, 200, 250, 300, 350, 400, 450, 500]
        result = criterio_de_bonello(frecuencias)
        self.assertIsInstance(result, dict)
        self.assertTrue(all(isinstance(k, float) and isinstance(v, int) for k, v in result.items()))

if __name__ == '__main__':
    unittest.main()

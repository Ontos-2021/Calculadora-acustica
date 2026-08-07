import unittest
from app import create_app


class TestRoutes(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    def test_index_get(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Calculadora Ac', response.data)

    def test_results_valid(self):
        response = self.client.post('/results', data={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'alfa_1': 0.1, 'alfa_2': 0.1, 'alfa_3': 0.1,
            'alfa_4': 0.1, 'alfa_5': 0.1, 'alfa_6': 0.1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'RT60', response.data)

    def test_results_invalid_dimensions(self):
        response = self.client.post('/results', data={
            'largo': -1, 'ancho': 4, 'alto': 3,
            'alfa_1': 0.1, 'alfa_2': 0.1, 'alfa_3': 0.1,
            'alfa_4': 0.1, 'alfa_5': 0.1, 'alfa_6': 0.1,
        })
        self.assertEqual(response.status_code, 302)

    def test_results_invalid_alfa(self):
        response = self.client.post('/results', data={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'alfa_1': 1.5, 'alfa_2': 0.1, 'alfa_3': 0.1,
            'alfa_4': 0.1, 'alfa_5': 0.1, 'alfa_6': 0.1,
        })
        self.assertEqual(response.status_code, 302)

    def test_results_non_numeric(self):
        response = self.client.post('/results', data={
            'largo': 'abc', 'ancho': 4, 'alto': 3,
            'alfa_1': 0.1, 'alfa_2': 0.1, 'alfa_3': 0.1,
            'alfa_4': 0.1, 'alfa_5': 0.1, 'alfa_6': 0.1,
        })
        self.assertEqual(response.status_code, 302)

    def test_api_calculate(self):
        response = self.client.post('/api/calculate', json={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'alfas': [0.1, 0.1, 0.1, 0.1, 0.1, 0.1],
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn('rt60', data)
        self.assertIn('modos_resonancia', data)
        self.assertIn('bonello', data)

    def test_api_invalid(self):
        response = self.client.post('/api/calculate', json={'largo': -1})
        self.assertEqual(response.status_code, 400)

    def test_api_missing_alfas(self):
        response = self.client.post('/api/calculate', json={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'alfas': [0.1],
        })
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()

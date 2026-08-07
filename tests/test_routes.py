import json


class TestRoutes:
    def test_index_get(self, client):
        response = client.get('/')
        assert response.status_code == 200
        assert b'Calculadora Ac' in response.data

    def test_results_valid(self, client):
        response = client.post('/results', data={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'material_1': 'Concreto', 'material_2': 'Concreto',
            'material_3': 'Concreto', 'material_4': 'Concreto',
            'material_5': 'Concreto', 'material_6': 'Concreto',
        })
        assert response.status_code == 200
        assert b'RT60' in response.data
        assert b'Schroeder' in response.data
        assert b'Bonello' in response.data

    def test_results_invalid_dimensions(self, client):
        response = client.post('/results', data={
            'largo': -1, 'ancho': 4, 'alto': 3,
            'material_1': 'Concreto',
        })
        assert response.status_code == 302

    def test_results_non_numeric(self, client):
        response = client.post('/results', data={
            'largo': 'abc', 'ancho': 4, 'alto': 3,
            'material_1': 'Concreto',
        })
        assert response.status_code == 302

    def test_results_with_uso(self, client):
        response = client.post('/results', data={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'material_1': 'Concreto', 'material_2': 'Concreto',
            'material_3': 'Concreto', 'material_4': 'Concreto',
            'material_5': 'Concreto', 'material_6': 'Concreto',
            'uso': 'home_studio',
        })
        assert response.status_code == 200
        assert b'Objetivo' in response.data

    def test_api_v1_calculate(self, client):
        response = client.post('/api/v1/calculate', json={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'superficies': [
                {'material': 'Concreto'},
                {'material': 'Concreto'},
                {'material': 'Yeso'},
                {'material': 'Yeso'},
                {'material': 'Alfombra gruesa'},
                {'material': 'Panel acústico'},
            ],
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'rt60_bandas' in data
        assert 'modos' in data
        assert 'bonello' in data
        assert 'f_schroeder' in data
        assert 'proporciones' in data

    def test_api_v1_invalid(self, client):
        response = client.post('/api/v1/calculate', json={'largo': -1})
        assert response.status_code == 400

    def test_api_v1_no_json(self, client):
        response = client.post('/api/v1/calculate', data='not json')
        assert response.status_code == 400

    def test_api_v1_custom_alphas(self, client):
        response = client.post('/api/v1/calculate', json={
            'largo': 5, 'ancho': 4, 'alto': 3,
            'superficies': [
                {'material': 'Concreto', 'alphas': {'125': 0.5, '500': 0.3}},
                {'material': 'Concreto'},
                {'material': 'Concreto'},
                {'material': 'Concreto'},
                {'material': 'Concreto'},
                {'material': 'Concreto'},
            ],
        })
        assert response.status_code == 200

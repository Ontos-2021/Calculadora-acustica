from api.schemas import CalculateRequest


class TestAPI:
    def test_health(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_calculate_valid(self, client):
        response = client.post("/api/v1/calculate", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [
                {"material": "Concreto"},
                {"material": "Concreto"},
                {"material": "Concreto"},
                {"material": "Concreto"},
                {"material": "Concreto"},
                {"material": "Concreto"},
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert "modos" in data
        assert "rt60_bandas" in data
        assert "bonello" in data
        assert "f_schroeder" in data
        assert "proporciones" in data
        assert len(data["modos"]) == 124

    def test_calculate_with_uso(self, client):
        response = client.post("/api/v1/calculate", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "uso": "home_studio",
            "superficies": [{"material": "Concreto"}] * 6,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["objetivo"] is not None
        assert "diferencias" in data["objetivo"]

    def test_calculate_custom_alphas(self, client):
        response = client.post("/api/v1/calculate", json={
            "largo": 5, "ancho": 4, "alto": 3,
            "superficies": [
                {"material": "Concreto", "alphas": {"125": 0.5, "500": 0.3}},
                {"material": "Concreto"},
                {"material": "Concreto"},
                {"material": "Concreto"},
                {"material": "Concreto"},
                {"material": "Concreto"},
            ],
        })
        assert response.status_code == 200

    def test_invalid_dimensions(self, client):
        response = client.post("/api/v1/calculate", json={
            "largo": -1, "ancho": 4, "alto": 3,
            "superficies": [{"material": "Concreto"}] * 6,
        })
        assert response.status_code == 422

    def test_invalid_no_data(self, client):
        response = client.post("/api/v1/calculate", json={})
        assert response.status_code == 422

    def test_materials_endpoint(self, client):
        response = client.get("/api/v1/materials")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 5
        assert any(m["nombre"] == "Concreto" for m in data)

    def test_ratios_endpoint(self, client):
        response = client.get("/api/v1/design/ratios")
        assert response.status_code == 200
        data = response.json()
        assert "Golden Ratio" in data

    def test_targets_endpoint(self, client):
        response = client.get("/api/v1/design/targets")
        assert response.status_code == 200
        data = response.json()
        assert "home_studio" in data

    def test_materials_categories(self, client):
        response = client.get("/api/v1/materials/categories")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) >= 8

    def test_material_detail(self, client):
        response = client.get("/api/v1/materials/Concreto")
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Concreto"
        assert "alphas" in data
        assert "alpha_w" in data
        assert "categoria" in data

    def test_material_detail_not_found(self, client):
        response = client.get("/api/v1/materials/NoExiste")
        assert response.status_code == 404

    def test_materials_search_by_category(self, client):
        response = client.get("/api/v1/materials?categoria=Espumas")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2

    def test_air_absorption(self, client):
        response = client.post("/api/v1/design/air-absorption", json={
            "humidity": 50, "temp_celsius": 20,
        })
        assert response.status_code == 200
        data = response.json()
        assert "coeficientes" in data
        assert len(data["coeficientes"]) == 6

    def test_audience_absorption(self, client):
        response = client.post("/api/v1/design/audience-absorption", json={
            "num_people": 10,
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6
        assert all(v > 0 for v in data.values())

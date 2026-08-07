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
        assert "Concreto" in data

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

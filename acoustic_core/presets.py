from .models import Material

MATERIALES_PRESETS = {
    "Concreto": Material(
        nombre="Concreto",
        alphas={"125": 0.01, "250": 0.02, "500": 0.04, "1000": 0.06, "2000": 0.08, "4000": 0.10},
    ),
    "Madera": Material(
        nombre="Madera",
        alphas={"125": 0.04, "250": 0.04, "500": 0.07, "1000": 0.06, "2000": 0.06, "4000": 0.07},
    ),
    "Yeso": Material(
        nombre="Yeso",
        alphas={"125": 0.10, "250": 0.08, "500": 0.05, "1000": 0.04, "2000": 0.04, "4000": 0.05},
    ),
    "Vidrio": Material(
        nombre="Vidrio",
        alphas={"125": 0.03, "250": 0.03, "500": 0.05, "1000": 0.08, "2000": 0.10, "4000": 0.10},
    ),
    "Alfombra gruesa": Material(
        nombre="Alfombra gruesa",
        alphas={"125": 0.08, "250": 0.24, "500": 0.57, "1000": 0.69, "2000": 0.71, "4000": 0.73},
    ),
    "Cortina pesada": Material(
        nombre="Cortina pesada",
        alphas={"125": 0.10, "250": 0.30, "500": 0.50, "1000": 0.65, "2000": 0.70, "4000": 0.70},
    ),
    "Panel acústico": Material(
        nombre="Panel acústico",
        alphas={"125": 0.20, "250": 0.60, "500": 0.85, "1000": 0.90, "2000": 0.85, "4000": 0.80},
    ),
    "Espuma acústica": Material(
        nombre="Espuma acústica",
        alphas={"125": 0.10, "250": 0.25, "500": 0.55, "1000": 0.70, "2000": 0.75, "4000": 0.70},
    ),
}

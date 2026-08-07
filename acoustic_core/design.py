from .models import BANDAS_OCTAVA


RT60_OBJETIVOS = {
    "home_studio": {
        "label": "Home Studio / Grabación",
        "valores": {"125": 0.30, "250": 0.30, "500": 0.30, "1000": 0.30, "2000": 0.30, "4000": 0.30},
    },
    "sala_conferencias": {
        "label": "Sala de conferencias",
        "valores": {"125": 0.70, "250": 0.70, "500": 0.70, "1000": 0.70, "2000": 0.70, "4000": 0.70},
    },
    "aula": {
        "label": "Aula",
        "valores": {"125": 0.75, "250": 0.75, "500": 0.80, "1000": 0.80, "2000": 0.80, "4000": 0.75},
    },
    "teatro": {
        "label": "Teatro",
        "valores": {"125": 1.00, "250": 1.00, "500": 1.00, "1000": 1.00, "2000": 1.00, "4000": 0.90},
    },
    "sala_conciertos": {
        "label": "Sala de conciertos",
        "valores": {"125": 1.80, "250": 1.80, "500": 1.80, "1000": 1.80, "2000": 1.60, "4000": 1.40},
    },
    "iglesia": {
        "label": "Iglesia / Culto",
        "valores": {"125": 2.20, "250": 2.20, "500": 2.20, "1000": 2.20, "2000": 2.00, "4000": 1.80},
    },
    "home_theater": {
        "label": "Home Theater",
        "valores": {"125": 0.40, "250": 0.40, "500": 0.40, "1000": 0.40, "2000": 0.40, "4000": 0.40},
    },
    "restaurante": {
        "label": "Restaurante",
        "valores": {"125": 0.50, "250": 0.50, "500": 0.60, "1000": 0.60, "2000": 0.60, "4000": 0.50},
    },
}


PROPORCIONES = {
    "Golden Ratio": (1, 1.25, 1.60),
    "Louden (1971)": (1, 1.14, 1.39),
    "Sepmeyer": (1, 1.19, 1.46),
    "Bonello": (1, 1.28, 1.54),
    "Volkmann": (1, 1.26, 1.59),
}


def get_rt60_target(uso: str) -> dict | None:
    if uso in RT60_OBJETIVOS:
        return RT60_OBJETIVOS[uso]
    return None


def find_closest_ratio(largo: float, ancho: float, alto: float) -> dict:
    dims = sorted([largo, ancho, alto])
    proporcion_actual = (1, round(dims[1] / dims[0], 2), round(dims[2] / dims[0], 2))

    mejores = []
    for nombre, (r1, r2, r3) in PROPORCIONES.items():
        error = abs(proporcion_actual[1] - r2) + abs(proporcion_actual[2] - r3)
        mejores.append((error, nombre, r2, r3))

    mejores.sort()
    mejor = mejores[0]

    return {
        "proporcion_actual": proporcion_actual,
        "mas_cercana": mejor[1],
        "proporcion_cercana": (1, mejor[2], mejor[3]),
        "error": round(mejor[0], 3),
        "todas": [(n, r2, r3) for _, n, r2, r3 in mejores],
    }

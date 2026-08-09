from dataclasses import dataclass
import math

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


# Coordinates are (middle / shortest, longest / shortest).  The practical
# published Bolt bounds are intersected with the normalized y >= x half-plane.
BOLT_AREA_POLYGON = (
    (1.1, 1.4),
    (1.4, 1.4),
    (1.9, 1.9),
    (1.9, 2.8),
    (1.1, 2.8),
)
DIMENSION_CONVENTION = "shortest:middle:longest (orientation-independent)"


@dataclass(frozen=True, slots=True)
class BoltAreaResult:
    normalized_ratio: tuple[float, float, float]
    is_inside: bool
    distance: float
    nearest_ratio: tuple[float, float, float]


def _validate_dimension(value: float, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    converted = float(value)
    if not math.isfinite(converted) or converted <= 0.0:
        raise ValueError(f"{name} must be finite and positive")
    return converted


def _normalized_dimensions(largo: float, ancho: float, alto: float) -> tuple[float, float, float]:
    dimensions = sorted(
        (
            _validate_dimension(largo, "largo"),
            _validate_dimension(ancho, "ancho"),
            _validate_dimension(alto, "alto"),
        )
    )
    middle = dimensions[1] / dimensions[0]
    largest = dimensions[2] / dimensions[0]
    if not math.isfinite(middle) or not math.isfinite(largest):
        raise OverflowError("normalized room ratios exceed finite floating-point range")
    return 1.0, middle, largest


def _nearest_point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0.0:
        return start
    projection = (
        (point[0] - start[0]) * dx + (point[1] - start[1]) * dy
    ) / length_squared
    projection = min(1.0, max(0.0, projection))
    return start[0] + projection * dx, start[1] + projection * dy


def is_in_bolt_area(middle_ratio: float, largest_ratio: float) -> bool:
    middle = _validate_dimension(middle_ratio, "middle_ratio")
    largest = _validate_dimension(largest_ratio, "largest_ratio")
    if middle > largest:
        raise ValueError("normalized ratios must satisfy middle_ratio <= largest_ratio")
    return 1.1 <= middle <= 1.9 and 1.4 <= largest <= 2.8


def _bolt_area_projection(
    middle_ratio: float,
    largest_ratio: float,
) -> tuple[float, tuple[float, float]]:
    middle = _validate_dimension(middle_ratio, "middle_ratio")
    largest = _validate_dimension(largest_ratio, "largest_ratio")
    if middle > largest:
        raise ValueError("normalized ratios must satisfy middle_ratio <= largest_ratio")
    point = (middle, largest)
    if is_in_bolt_area(middle, largest):
        return 0.0, point

    candidates = []
    for index, start in enumerate(BOLT_AREA_POLYGON):
        end = BOLT_AREA_POLYGON[(index + 1) % len(BOLT_AREA_POLYGON)]
        nearest = _nearest_point_on_segment(point, start, end)
        distance = math.hypot(point[0] - nearest[0], point[1] - nearest[1])
        candidates.append((distance, nearest))
    return min(candidates, key=lambda candidate: candidate[0])


def bolt_area_distance(middle_ratio: float, largest_ratio: float) -> float:
    """Return Euclidean distance to the Bolt area in normalized ratio space."""

    return _bolt_area_projection(middle_ratio, largest_ratio)[0]


def evaluate_bolt_area(largo: float, ancho: float, alto: float) -> BoltAreaResult:
    normalized = _normalized_dimensions(largo, ancho, alto)
    distance, nearest = _bolt_area_projection(normalized[1], normalized[2])
    return BoltAreaResult(
        normalized_ratio=normalized,
        is_inside=distance == 0.0,
        distance=distance,
        nearest_ratio=(1.0, nearest[0], nearest[1]),
    )


def _integer_multiples(
    largo: float,
    ancho: float,
    alto: float,
    tolerance: float = 0.01,
) -> tuple[tuple[str, str, int], ...]:
    dimensions = (
        ("largo", _validate_dimension(largo, "largo")),
        ("ancho", _validate_dimension(ancho, "ancho")),
        ("alto", _validate_dimension(alto, "alto")),
    )
    multiples: list[tuple[str, str, int]] = []
    for index, (first_name, first) in enumerate(dimensions):
        for second_name, second in dimensions[index + 1 :]:
            if first >= second:
                larger_name, larger = first_name, first
                smaller_name, smaller = second_name, second
            else:
                larger_name, larger = second_name, second
                smaller_name, smaller = first_name, first
            ratio = larger / smaller
            integer = round(ratio)
            if integer >= 2 and abs(ratio - integer) <= tolerance:
                multiples.append((larger_name, smaller_name, integer))
    return tuple(multiples)


def get_rt60_target(uso: str) -> dict | None:
    if uso in RT60_OBJETIVOS:
        return RT60_OBJETIVOS[uso]
    return None


def find_closest_ratio(largo: float, ancho: float, alto: float) -> dict:
    proporcion_actual = _normalized_dimensions(largo, ancho, alto)
    bolt = evaluate_bolt_area(largo, ancho, alto)

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
        "error": mejor[0],
        "todas": [(n, r2, r3) for _, n, r2, r3 in mejores],
        "en_area_bolt": bolt.is_inside,
        "distancia_area_bolt": bolt.distance,
        "proporcion_bolt_mas_cercana": bolt.nearest_ratio,
        "convencion_dimensiones": DIMENSION_CONVENTION,
        "multiplos_enteros": list(_integer_multiples(largo, ancho, alto)),
    }

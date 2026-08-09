"""Deterministic, band-resolved geometric-acoustics path tracing.

Finite geometry is represented by triangles accelerated with a binned surface
area heuristic (SAH) BVH.  Infinite planes are also supported and are tested
outside the BVH.  Listener capture uses exact segment/sphere intersections for
specular paths and next-event estimation for diffuse scattering; direct sound is
always evaluated explicitly when visible.

The implementation is a research transport model.  It does not model diffraction,
phase interference, finite source directivity, or wave effects, and should only be
used above an independently justified geometric-acoustics crossover frequency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Mapping, Sequence, TypeAlias

import numpy as np


CoefficientSpec: TypeAlias = float | Sequence[float] | Mapping[str | float | int, float]


def _as_vector3(value: Sequence[float], name: str) -> np.ndarray:
    vector = np.asarray(value, dtype=float)
    if vector.shape != (3,) or not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain three finite coordinates")
    return vector


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise ValueError("direction or normal vector must be non-zero")
    return vector / norm


def _band_key(frequency_hz: float) -> str:
    rounded = round(float(frequency_hz))
    if abs(float(frequency_hz) - rounded) <= 1e-9:
        return str(int(rounded))
    return f"{float(frequency_hz):g}"


def _coefficient_values(
    specification: CoefficientSpec,
    bands_hz: np.ndarray,
    name: str,
    *,
    upper_bound: float | None,
) -> np.ndarray:
    if isinstance(specification, Mapping):
        numeric: list[tuple[float, float]] = []
        default = None
        for key, value in specification.items():
            if str(key).lower() == "default":
                default = float(value)
                continue
            try:
                numeric.append((float(key), float(value)))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{name} mapping keys must be numeric frequencies") from exc
        if numeric:
            numeric.sort(key=lambda item: item[0])
            source_frequencies = np.asarray([item[0] for item in numeric], dtype=float)
            source_values = np.asarray([item[1] for item in numeric], dtype=float)
            if np.any(source_frequencies <= 0.0):
                raise ValueError(f"{name} frequency keys must be positive")
            values = np.interp(
                np.log(bands_hz),
                np.log(source_frequencies),
                source_values,
                left=source_values[0] if default is None else default,
                right=source_values[-1] if default is None else default,
            )
        elif default is not None:
            values = np.full(len(bands_hz), default, dtype=float)
        else:
            raise ValueError(f"{name} mapping cannot be empty")
    elif np.isscalar(specification):
        values = np.full(len(bands_hz), float(specification), dtype=float)
    else:
        values = np.asarray(specification, dtype=float)
        if values.shape != bands_hz.shape:
            raise ValueError(f"{name} sequence must match bands_hz")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError(f"{name} coefficients must be finite and non-negative")
    if upper_bound is not None and np.any(values > upper_bound):
        raise ValueError(f"{name} coefficients must not exceed {upper_bound}")
    return values


@dataclass(frozen=True)
class BandMaterial:
    """Frequency-dependent energy absorption and scattering coefficients."""

    absorption: CoefficientSpec = 0.0
    scattering: CoefficientSpec = 0.0

    def coefficients(self, bands_hz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        absorption = _coefficient_values(self.absorption, bands_hz, "absorption", upper_bound=1.0)
        scattering = _coefficient_values(self.scattering, bands_hz, "scattering", upper_bound=1.0)
        return absorption, scattering


@dataclass(frozen=True)
class TriangleSurface:
    vertices: Sequence[Sequence[float]]
    surface_id: str
    material: BandMaterial = field(default_factory=BandMaterial)

    def __post_init__(self) -> None:
        vertices = np.asarray(self.vertices, dtype=float)
        if vertices.shape != (3, 3) or not np.all(np.isfinite(vertices)):
            raise ValueError("triangle vertices must have shape (3, 3) and be finite")
        if np.linalg.norm(np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0])) <= 1e-14:
            raise ValueError("triangle vertices must not be collinear")
        object.__setattr__(self, "vertices", vertices.copy())
        if not self.surface_id:
            raise ValueError("surface_id must not be empty")


@dataclass(frozen=True)
class PlaneSurface:
    """An infinite two-sided plane; use triangles for finite surfaces."""

    point: Sequence[float]
    normal: Sequence[float]
    surface_id: str
    material: BandMaterial = field(default_factory=BandMaterial)

    def __post_init__(self) -> None:
        object.__setattr__(self, "point", _as_vector3(self.point, "plane point"))
        object.__setattr__(self, "normal", _normalize(_as_vector3(self.normal, "plane normal")))
        if not self.surface_id:
            raise ValueError("surface_id must not be empty")


@dataclass(frozen=True)
class Intersection:
    distance_m: float
    point: np.ndarray
    normal: np.ndarray
    surface_id: str
    material: BandMaterial
    primitive_kind: str
    primitive_index: int


@dataclass
class _BVHNode:
    minimum: np.ndarray
    maximum: np.ndarray
    left: int = -1
    right: int = -1
    primitive_indices: np.ndarray | None = None

    @property
    def is_leaf(self) -> bool:
        return self.primitive_indices is not None


def _box_surface_area(minimum: np.ndarray, maximum: np.ndarray) -> float:
    extent = np.maximum(0.0, maximum - minimum)
    return float(2.0 * (extent[0] * extent[1] + extent[1] * extent[2] + extent[2] * extent[0]))


class BVH:
    """Triangle BVH built using a 12-bin surface area heuristic."""

    def __init__(self, triangles: Sequence[TriangleSurface], leaf_size: int = 4, sah_bins: int = 12) -> None:
        if leaf_size < 1 or sah_bins < 2:
            raise ValueError("leaf_size must be positive and sah_bins must be at least 2")
        self.triangles = tuple(triangles)
        self.leaf_size = leaf_size
        self.sah_bins = sah_bins
        self.nodes: list[_BVHNode] = []
        self.split_strategy = "binned SAH"
        if not self.triangles:
            self._vertices = np.empty((0, 3, 3), dtype=float)
            self._minimum = np.empty((0, 3), dtype=float)
            self._maximum = np.empty((0, 3), dtype=float)
            self._centroids = np.empty((0, 3), dtype=float)
            return
        self._vertices = np.asarray([triangle.vertices for triangle in self.triangles], dtype=float)
        self._minimum = np.min(self._vertices, axis=1)
        self._maximum = np.max(self._vertices, axis=1)
        self._centroids = np.mean(self._vertices, axis=1)
        self._build(np.arange(len(self.triangles), dtype=np.int64))

    def _build(self, indices: np.ndarray) -> int:
        minimum = np.min(self._minimum[indices], axis=0)
        maximum = np.max(self._maximum[indices], axis=0)
        node_index = len(self.nodes)
        self.nodes.append(_BVHNode(minimum=minimum, maximum=maximum))
        if len(indices) <= self.leaf_size:
            self.nodes[node_index].primitive_indices = indices.copy()
            return node_index

        parent_area = max(_box_surface_area(minimum, maximum), np.finfo(float).eps)
        leaf_cost = len(indices) * parent_area
        best_cost = math.inf
        best_axis = -1
        best_split_bin = -1
        best_centroid_minimum = 0.0
        best_centroid_extent = 0.0

        for axis in range(3):
            centroids = self._centroids[indices, axis]
            centroid_minimum = float(np.min(centroids))
            centroid_extent = float(np.max(centroids) - centroid_minimum)
            if centroid_extent <= 1e-14:
                continue
            bin_count = min(self.sah_bins, len(indices))
            assignments = np.minimum(
                bin_count - 1,
                ((centroids - centroid_minimum) / centroid_extent * bin_count).astype(np.int64),
            )
            counts = np.zeros(bin_count, dtype=np.int64)
            bin_minimum = np.full((bin_count, 3), math.inf)
            bin_maximum = np.full((bin_count, 3), -math.inf)
            for local_index, primitive_index in enumerate(indices):
                bin_index = int(assignments[local_index])
                counts[bin_index] += 1
                bin_minimum[bin_index] = np.minimum(bin_minimum[bin_index], self._minimum[primitive_index])
                bin_maximum[bin_index] = np.maximum(bin_maximum[bin_index], self._maximum[primitive_index])

            left_counts = np.cumsum(counts)
            right_counts = np.cumsum(counts[::-1])[::-1]
            left_minimum = np.full((bin_count, 3), math.inf)
            left_maximum = np.full((bin_count, 3), -math.inf)
            right_minimum = np.full((bin_count, 3), math.inf)
            right_maximum = np.full((bin_count, 3), -math.inf)
            for bin_index in range(bin_count):
                if bin_index == 0:
                    left_minimum[bin_index] = bin_minimum[bin_index]
                    left_maximum[bin_index] = bin_maximum[bin_index]
                else:
                    left_minimum[bin_index] = np.minimum(left_minimum[bin_index - 1], bin_minimum[bin_index])
                    left_maximum[bin_index] = np.maximum(left_maximum[bin_index - 1], bin_maximum[bin_index])
            for bin_index in range(bin_count - 1, -1, -1):
                if bin_index == bin_count - 1:
                    right_minimum[bin_index] = bin_minimum[bin_index]
                    right_maximum[bin_index] = bin_maximum[bin_index]
                else:
                    right_minimum[bin_index] = np.minimum(right_minimum[bin_index + 1], bin_minimum[bin_index])
                    right_maximum[bin_index] = np.maximum(right_maximum[bin_index + 1], bin_maximum[bin_index])

            for split_bin in range(bin_count - 1):
                if left_counts[split_bin] == 0 or right_counts[split_bin + 1] == 0:
                    continue
                cost = (
                    left_counts[split_bin] * _box_surface_area(left_minimum[split_bin], left_maximum[split_bin])
                    + right_counts[split_bin + 1]
                    * _box_surface_area(right_minimum[split_bin + 1], right_maximum[split_bin + 1])
                )
                if cost < best_cost:
                    best_cost = float(cost)
                    best_axis = axis
                    best_split_bin = split_bin
                    best_centroid_minimum = centroid_minimum
                    best_centroid_extent = centroid_extent

        if best_axis < 0 or best_cost >= leaf_cost:
            axis = int(np.argmax(np.ptp(self._centroids[indices], axis=0)))
            ordered = indices[np.argsort(self._centroids[indices, axis])]
            middle = len(ordered) // 2
            left_indices, right_indices = ordered[:middle], ordered[middle:]
        else:
            bin_count = min(self.sah_bins, len(indices))
            assignments = np.minimum(
                bin_count - 1,
                (
                    (self._centroids[indices, best_axis] - best_centroid_minimum)
                    / best_centroid_extent
                    * bin_count
                ).astype(np.int64),
            )
            mask = assignments <= best_split_bin
            left_indices, right_indices = indices[mask], indices[~mask]
            if len(left_indices) == 0 or len(right_indices) == 0:
                ordered = indices[np.argsort(self._centroids[indices, best_axis])]
                middle = len(ordered) // 2
                left_indices, right_indices = ordered[:middle], ordered[middle:]

        if len(left_indices) == 0 or len(right_indices) == 0:
            self.nodes[node_index].primitive_indices = indices.copy()
            return node_index
        self.nodes[node_index].left = self._build(left_indices)
        self.nodes[node_index].right = self._build(right_indices)
        return node_index

    @staticmethod
    def _box_intersection(
        origin: np.ndarray,
        direction: np.ndarray,
        minimum: np.ndarray,
        maximum: np.ndarray,
        minimum_distance: float,
        maximum_distance: float,
    ) -> bool:
        near, far = minimum_distance, maximum_distance
        for axis in range(3):
            if abs(direction[axis]) <= 1e-15:
                if origin[axis] < minimum[axis] or origin[axis] > maximum[axis]:
                    return False
                continue
            inverse = 1.0 / direction[axis]
            first = (minimum[axis] - origin[axis]) * inverse
            second = (maximum[axis] - origin[axis]) * inverse
            if first > second:
                first, second = second, first
            near = max(near, first)
            far = min(far, second)
            if far < near:
                return False
        return True

    def intersect(
        self,
        origin: Sequence[float],
        direction: Sequence[float],
        *,
        minimum_distance: float = 1e-7,
        maximum_distance: float = math.inf,
        statistics: dict[str, int] | None = None,
    ) -> tuple[float, int] | None:
        """Return ``(distance, triangle_index)`` for the closest hit."""

        if not self.nodes:
            return None
        ray_origin = _as_vector3(origin, "ray origin")
        ray_direction = _normalize(_as_vector3(direction, "ray direction"))
        closest = maximum_distance
        closest_index = -1
        stack = [0]
        while stack:
            node_index = stack.pop()
            node = self.nodes[node_index]
            if statistics is not None:
                statistics["bvh_node_tests"] = statistics.get("bvh_node_tests", 0) + 1
            if not self._box_intersection(
                ray_origin,
                ray_direction,
                node.minimum,
                node.maximum,
                minimum_distance,
                closest,
            ):
                continue
            if node.is_leaf:
                assert node.primitive_indices is not None
                for primitive_index in node.primitive_indices:
                    if statistics is not None:
                        statistics["triangle_tests"] = statistics.get("triangle_tests", 0) + 1
                    vertices = self._vertices[primitive_index]
                    edge1 = vertices[1] - vertices[0]
                    edge2 = vertices[2] - vertices[0]
                    cross = np.cross(ray_direction, edge2)
                    determinant = float(np.dot(edge1, cross))
                    if abs(determinant) <= 1e-12:
                        continue
                    inverse_determinant = 1.0 / determinant
                    offset = ray_origin - vertices[0]
                    u = float(np.dot(offset, cross) * inverse_determinant)
                    if u < 0.0 or u > 1.0:
                        continue
                    q = np.cross(offset, edge1)
                    v = float(np.dot(ray_direction, q) * inverse_determinant)
                    if v < 0.0 or u + v > 1.0:
                        continue
                    distance = float(np.dot(edge2, q) * inverse_determinant)
                    if minimum_distance < distance < closest:
                        closest = distance
                        closest_index = int(primitive_index)
            else:
                stack.append(node.left)
                stack.append(node.right)
        return (closest, closest_index) if closest_index >= 0 else None


@dataclass
class AcousticScene:
    triangles: Sequence[TriangleSurface] = field(default_factory=tuple)
    planes: Sequence[PlaneSurface] = field(default_factory=tuple)
    bvh: BVH = field(init=False)

    def __post_init__(self) -> None:
        self.triangles = tuple(self.triangles)
        self.planes = tuple(self.planes)
        if not self.triangles and not self.planes:
            raise ValueError("scene must contain at least one triangle or plane")
        self.bvh = BVH(self.triangles)

    def intersect(
        self,
        origin: Sequence[float],
        direction: Sequence[float],
        *,
        minimum_distance: float = 1e-7,
        maximum_distance: float = math.inf,
        statistics: dict[str, int] | None = None,
    ) -> Intersection | None:
        ray_origin = _as_vector3(origin, "ray origin")
        ray_direction = _normalize(_as_vector3(direction, "ray direction"))
        closest = maximum_distance
        result: Intersection | None = None
        triangle_hit = self.bvh.intersect(
            ray_origin,
            ray_direction,
            minimum_distance=minimum_distance,
            maximum_distance=closest,
            statistics=statistics,
        )
        if triangle_hit is not None:
            closest, primitive_index = triangle_hit
            triangle = self.triangles[primitive_index]
            vertices = np.asarray(triangle.vertices)
            normal = _normalize(np.cross(vertices[1] - vertices[0], vertices[2] - vertices[0]))
            if np.dot(normal, ray_direction) > 0.0:
                normal = -normal
            result = Intersection(
                distance_m=closest,
                point=ray_origin + closest * ray_direction,
                normal=normal,
                surface_id=triangle.surface_id,
                material=triangle.material,
                primitive_kind="triangle",
                primitive_index=primitive_index,
            )

        for primitive_index, plane in enumerate(self.planes):
            if statistics is not None:
                statistics["plane_tests"] = statistics.get("plane_tests", 0) + 1
            denominator = float(np.dot(ray_direction, plane.normal))
            if abs(denominator) <= 1e-14:
                continue
            distance = float(np.dot(np.asarray(plane.point) - ray_origin, plane.normal) / denominator)
            if not (minimum_distance < distance < closest):
                continue
            closest = distance
            normal = np.asarray(plane.normal).copy()
            if np.dot(normal, ray_direction) > 0.0:
                normal = -normal
            result = Intersection(
                distance_m=distance,
                point=ray_origin + distance * ray_direction,
                normal=normal,
                surface_id=plane.surface_id,
                material=plane.material,
                primitive_kind="plane",
                primitive_index=primitive_index,
            )
        return result

    def visible(self, start: Sequence[float], end: Sequence[float], epsilon: float = 1e-6) -> bool:
        start_point = _as_vector3(start, "visibility start")
        end_point = _as_vector3(end, "visibility end")
        offset = end_point - start_point
        distance = float(np.linalg.norm(offset))
        if distance <= epsilon:
            return True
        hit = self.intersect(
            start_point,
            offset / distance,
            minimum_distance=epsilon,
            maximum_distance=max(epsilon, distance - epsilon),
        )
        return hit is None


def shoebox_scene(
    dimensions_m: Sequence[float],
    materials: Sequence[BandMaterial] | BandMaterial | None = None,
    surface_ids: Sequence[str] = ("x0", "x1", "y0", "y1", "z0", "z1"),
) -> AcousticScene:
    """Build a six-plane closed shoebox scene.

    Surface order is ``x=0, x=L, y=0, y=W, z=0, z=H``.
    """

    dimensions = _as_vector3(dimensions_m, "shoebox dimensions")
    if np.any(dimensions <= 0.0):
        raise ValueError("shoebox dimensions must be positive")
    if len(surface_ids) != 6:
        raise ValueError("surface_ids must contain six names")
    if materials is None:
        material_values = [BandMaterial()] * 6
    elif isinstance(materials, BandMaterial):
        material_values = [materials] * 6
    else:
        material_values = list(materials)
        if len(material_values) != 6:
            raise ValueError("materials must contain six BandMaterial objects")
    length, width, height = dimensions
    planes = [
        PlaneSurface((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), surface_ids[0], material_values[0]),
        PlaneSurface((length, 0.0, 0.0), (-1.0, 0.0, 0.0), surface_ids[1], material_values[1]),
        PlaneSurface((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), surface_ids[2], material_values[2]),
        PlaneSurface((0.0, width, 0.0), (0.0, -1.0, 0.0), surface_ids[3], material_values[3]),
        PlaneSurface((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), surface_ids[4], material_values[4]),
        PlaneSurface((0.0, 0.0, height), (0.0, 0.0, -1.0), surface_ids[5], material_values[5]),
    ]
    return AcousticScene(planes=planes)


def segment_sphere_intersection(
    segment_start: Sequence[float],
    segment_end: Sequence[float],
    sphere_center: Sequence[float],
    sphere_radius_m: float,
) -> float | None:
    """Return distance from segment start to the first listener-sphere hit."""

    if sphere_radius_m <= 0.0:
        raise ValueError("sphere_radius_m must be positive")
    start = _as_vector3(segment_start, "segment start")
    end = _as_vector3(segment_end, "segment end")
    center = _as_vector3(sphere_center, "sphere center")
    segment = end - start
    segment_length = float(np.linalg.norm(segment))
    if segment_length <= 0.0:
        return 0.0 if np.linalg.norm(start - center) <= sphere_radius_m else None
    direction = segment / segment_length
    offset = start - center
    projected = float(np.dot(offset, direction))
    constant = float(np.dot(offset, offset) - sphere_radius_m**2)
    discriminant = projected * projected - constant
    if discriminant < 0.0:
        return None
    root = math.sqrt(max(0.0, discriminant))
    first = -projected - root
    second = -projected + root
    if constant <= 0.0:
        return 0.0
    if 0.0 <= first <= segment_length:
        return first
    if 0.0 <= second <= segment_length:
        return second
    return None


@dataclass(frozen=True)
class RayTraceConfig:
    bands_hz: tuple[float, ...] = (125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0)
    num_rays: int = 1000
    max_reflections: int = 50
    max_time_s: float = 1.0
    listener_radius_m: float = 0.15
    time_bin_s: float = 0.001
    sound_speed_m_s: float = 343.0
    seed: int = 0
    minimum_packet_energy: float = 1e-12
    air_absorption_db_per_m: CoefficientSpec = 0.0

    def __post_init__(self) -> None:
        bands = np.asarray(self.bands_hz, dtype=float)
        if bands.ndim != 1 or len(bands) == 0 or np.any(bands <= 0.0) or not np.all(np.isfinite(bands)):
            raise ValueError("bands_hz must contain positive finite frequencies")
        if self.num_rays < 1 or self.max_reflections < 0:
            raise ValueError("num_rays must be positive and max_reflections non-negative")
        if self.max_time_s <= 0.0 or self.listener_radius_m <= 0.0 or self.time_bin_s <= 0.0:
            raise ValueError("time and listener-radius settings must be positive")
        if self.sound_speed_m_s <= 0.0 or self.minimum_packet_energy < 0.0:
            raise ValueError("sound speed must be positive and energy threshold non-negative")


@dataclass(frozen=True)
class RayArrival:
    time_s: float
    path_length_m: float
    energy_by_band: np.ndarray
    event: str
    reflection_count: int


@dataclass(frozen=True)
class SurfaceStatistics:
    hit_count: int
    diffuse_events: int
    incident_energy_by_band: np.ndarray
    absorbed_energy_by_band: np.ndarray


@dataclass(frozen=True)
class RayTraceResult:
    bands_hz: np.ndarray
    times_s: np.ndarray
    energy_by_band: np.ndarray
    energy_db_by_band: np.ndarray
    arrivals: tuple[RayArrival, ...]
    surface_statistics: Mapping[str, SurfaceStatistics]
    rt60_s_by_band: np.ndarray
    direct_time_s: float | None
    total_ray_segments: int
    terminated_ray_count: int
    seed: int
    bvh_statistics: Mapping[str, int]
    research_status: str

    @property
    def total_energy_by_band(self) -> np.ndarray:
        return np.sum(self.energy_by_band, axis=1)

    def to_dict(self) -> dict:
        return {
            "bands_hz": self.bands_hz.tolist(),
            "time_s": self.times_s.tolist(),
            "energy_by_band": {
                _band_key(band): self.energy_by_band[index].tolist()
                for index, band in enumerate(self.bands_hz)
            },
            "energy_db_by_band": {
                _band_key(band): self.energy_db_by_band[index].tolist()
                for index, band in enumerate(self.bands_hz)
            },
            "total_energy_by_band": {
                _band_key(band): float(self.total_energy_by_band[index])
                for index, band in enumerate(self.bands_hz)
            },
            "rt60_s_by_band": {
                _band_key(band): float(self.rt60_s_by_band[index])
                for index, band in enumerate(self.bands_hz)
            },
            "direct_time_s": self.direct_time_s,
            "total_ray_segments": self.total_ray_segments,
            "terminated_ray_count": self.terminated_ray_count,
            "seed": self.seed,
            "surface_statistics": {
                name: {
                    "hit_count": statistics.hit_count,
                    "diffuse_events": statistics.diffuse_events,
                    "incident_energy_by_band": statistics.incident_energy_by_band.tolist(),
                    "absorbed_energy_by_band": statistics.absorbed_energy_by_band.tolist(),
                }
                for name, statistics in self.surface_statistics.items()
            },
            "bvh_statistics": dict(self.bvh_statistics),
            "research_status": self.research_status,
        }


def _random_sphere_direction(generator: np.random.Generator) -> np.ndarray:
    z = 2.0 * generator.random() - 1.0
    azimuth = 2.0 * math.pi * generator.random()
    radius = math.sqrt(max(0.0, 1.0 - z * z))
    return np.asarray((radius * math.cos(azimuth), radius * math.sin(azimuth), z))


def _cosine_hemisphere_direction(normal: np.ndarray, generator: np.random.Generator) -> np.ndarray:
    radius = math.sqrt(generator.random())
    azimuth = 2.0 * math.pi * generator.random()
    local_x = radius * math.cos(azimuth)
    local_y = radius * math.sin(azimuth)
    local_z = math.sqrt(max(0.0, 1.0 - radius * radius))
    helper = np.asarray((0.0, 0.0, 1.0)) if abs(normal[2]) < 0.9 else np.asarray((1.0, 0.0, 0.0))
    tangent = _normalize(np.cross(helper, normal))
    bitangent = np.cross(normal, tangent)
    return _normalize(local_x * tangent + local_y * bitangent + local_z * normal)


def _air_factor(air_absorption_db_per_m: np.ndarray, distance_m: float) -> np.ndarray:
    return np.power(10.0, -air_absorption_db_per_m * distance_m / 10.0)


def _estimate_rt60(energy: np.ndarray, times_s: np.ndarray) -> float:
    decay = np.cumsum(energy[::-1])[::-1]
    if len(decay) < 3 or decay[0] <= 0.0:
        return 0.0
    decay_db = 10.0 * np.log10(np.maximum(decay / decay[0], 1e-30))
    mask = (decay_db <= -5.0) & (decay_db >= -25.0) & (energy + decay > 0.0)
    if np.count_nonzero(mask) < 3:
        return 0.0
    slope, _ = np.polyfit(times_s[mask], decay_db[mask], 1)
    if not np.isfinite(slope) or slope >= 0.0:
        return 0.0
    return float(-60.0 / slope)


def trace_scene(
    scene: AcousticScene,
    source: Sequence[float],
    listener: Sequence[float],
    config: RayTraceConfig | None = None,
    *,
    source_energy_by_band: CoefficientSpec = 1.0,
) -> RayTraceResult:
    """Trace a deterministic Monte Carlo geometric-acoustics response."""

    settings = config or RayTraceConfig()
    bands = np.asarray(settings.bands_hz, dtype=float)
    source_point = _as_vector3(source, "source")
    listener_point = _as_vector3(listener, "listener")
    source_energy = _coefficient_values(source_energy_by_band, bands, "source energy", upper_bound=None)
    air_absorption = _coefficient_values(
        settings.air_absorption_db_per_m,
        bands,
        "air absorption",
        upper_bound=None,
    )
    bin_count = int(math.ceil(settings.max_time_s / settings.time_bin_s)) + 1
    times = np.arange(bin_count, dtype=float) * settings.time_bin_s
    energy_histogram = np.zeros((len(bands), bin_count), dtype=float)
    arrivals: list[RayArrival] = []
    random_generator = np.random.default_rng(settings.seed)
    intersection_statistics: dict[str, int] = {}

    surface_materials: dict[str, BandMaterial] = {}
    for surface in (*scene.triangles, *scene.planes):
        surface_materials.setdefault(surface.surface_id, surface.material)
    mutable_surface_statistics = {
        surface_id: {
            "hit_count": 0,
            "diffuse_events": 0,
            "incident": np.zeros(len(bands), dtype=float),
            "absorbed": np.zeros(len(bands), dtype=float),
        }
        for surface_id in surface_materials
    }

    def deposit(
        event_time_s: float,
        path_length_m: float,
        event_energy: np.ndarray,
        event: str,
        reflection_count: int,
    ) -> None:
        if event_time_s < 0.0 or event_time_s > settings.max_time_s or not np.any(event_energy > 0.0):
            return
        bin_index = min(bin_count - 1, int(round(event_time_s / settings.time_bin_s)))
        finite_energy = np.maximum(0.0, np.asarray(event_energy, dtype=float))
        energy_histogram[:, bin_index] += finite_energy
        arrivals.append(
            RayArrival(
                time_s=float(event_time_s),
                path_length_m=float(path_length_m),
                energy_by_band=finite_energy.copy(),
                event=event,
                reflection_count=reflection_count,
            )
        )

    direct_offset = listener_point - source_point
    direct_distance = float(np.linalg.norm(direct_offset))
    direct_time: float | None = None
    if direct_distance > 0.0 and scene.visible(source_point, listener_point):
        direct_time = direct_distance / settings.sound_speed_m_s
        direct_energy = (
            source_energy
            * _air_factor(air_absorption, direct_distance)
            / (4.0 * math.pi * direct_distance * direct_distance)
        )
        deposit(direct_time, direct_distance, direct_energy, "direct", 0)

    total_segments = 0
    terminated_rays = 0
    listener_area = math.pi * settings.listener_radius_m**2
    maximum_path_length = settings.max_time_s * settings.sound_speed_m_s
    epsilon = max(1e-7, 1e-7 * maximum_path_length)

    for _ in range(settings.num_rays):
        position = source_point.copy()
        direction = _random_sphere_direction(random_generator)
        packet_energy = source_energy / settings.num_rays
        travelled_distance = 0.0
        previous_event_specular = True
        ray_terminated = False

        for reflection_count in range(settings.max_reflections):
            remaining_distance = maximum_path_length - travelled_distance
            if remaining_distance <= 0.0:
                ray_terminated = True
                break
            hit = scene.intersect(
                position,
                direction,
                minimum_distance=epsilon,
                maximum_distance=remaining_distance,
                statistics=intersection_statistics,
            )
            segment_distance = hit.distance_m if hit is not None else remaining_distance
            segment_end = position + segment_distance * direction
            total_segments += 1

            listener_hit_distance = segment_sphere_intersection(
                position,
                segment_end,
                listener_point,
                settings.listener_radius_m,
            )
            # Direct sound and diffuse next-event estimates are handled separately;
            # sphere capture completes the complementary specular estimator.
            if reflection_count > 0 and previous_event_specular and listener_hit_distance is not None:
                listener_path = travelled_distance + listener_hit_distance
                captured = (
                    packet_energy
                    * _air_factor(air_absorption, listener_hit_distance)
                    / listener_area
                )
                deposit(
                    listener_path / settings.sound_speed_m_s,
                    listener_path,
                    captured,
                    "specular_listener_sphere",
                    reflection_count,
                )

            packet_energy = packet_energy * _air_factor(air_absorption, segment_distance)
            travelled_distance += segment_distance
            if hit is None:
                ray_terminated = True
                break

            absorption, scattering = hit.material.coefficients(bands)
            surface_stats = mutable_surface_statistics[hit.surface_id]
            surface_stats["hit_count"] += 1
            surface_stats["incident"] += packet_energy
            absorbed = packet_energy * absorption
            surface_stats["absorbed"] += absorbed
            reflected_energy = packet_energy - absorbed

            listener_vector = listener_point - hit.point
            listener_distance = float(np.linalg.norm(listener_vector))
            if listener_distance > epsilon and np.any(scattering > 0.0):
                listener_direction = listener_vector / listener_distance
                cosine = max(0.0, float(np.dot(hit.normal, listener_direction)))
                visibility_start = hit.point + epsilon * listener_direction
                if cosine > 0.0 and scene.visible(visibility_start, listener_point, epsilon=epsilon):
                    diffuse_energy = (
                        reflected_energy
                        * scattering
                        * cosine
                        / (math.pi * listener_distance**2)
                        * _air_factor(air_absorption, listener_distance)
                    )
                    full_path = travelled_distance + listener_distance
                    deposit(
                        full_path / settings.sound_speed_m_s,
                        full_path,
                        diffuse_energy,
                        "diffuse_next_event",
                        reflection_count + 1,
                    )

            active_weight = float(np.sum(reflected_energy))
            if active_weight <= settings.minimum_packet_energy:
                ray_terminated = True
                break
            scattering_probability = float(np.dot(reflected_energy, scattering) / active_weight)
            scattering_probability = min(1.0, max(0.0, scattering_probability))
            if scattering_probability > 0.0 and random_generator.random() < scattering_probability:
                direction = _cosine_hemisphere_direction(hit.normal, random_generator)
                packet_energy = reflected_energy * scattering / scattering_probability
                previous_event_specular = False
                surface_stats["diffuse_events"] += 1
            else:
                direction = _normalize(direction - 2.0 * np.dot(direction, hit.normal) * hit.normal)
                if scattering_probability < 1.0:
                    packet_energy = reflected_energy * (1.0 - scattering) / (1.0 - scattering_probability)
                else:
                    packet_energy = np.zeros_like(reflected_energy)
                previous_event_specular = True
            position = hit.point + epsilon * direction

        if ray_terminated or np.sum(packet_energy) <= settings.minimum_packet_energy:
            terminated_rays += 1

    energy_db = np.full_like(energy_histogram, -120.0)
    for band_index in range(len(bands)):
        peak = float(np.max(energy_histogram[band_index]))
        if peak > 0.0:
            energy_db[band_index] = 10.0 * np.log10(
                np.maximum(energy_histogram[band_index] / peak, 1e-12)
            )
    rt60 = np.asarray(
        [_estimate_rt60(energy_histogram[index], times) for index in range(len(bands))],
        dtype=float,
    )
    surface_statistics = {
        surface_id: SurfaceStatistics(
            hit_count=int(values["hit_count"]),
            diffuse_events=int(values["diffuse_events"]),
            incident_energy_by_band=np.asarray(values["incident"], dtype=float),
            absorbed_energy_by_band=np.asarray(values["absorbed"], dtype=float),
        )
        for surface_id, values in mutable_surface_statistics.items()
    }
    return RayTraceResult(
        bands_hz=bands,
        times_s=times,
        energy_by_band=energy_histogram,
        energy_db_by_band=energy_db,
        arrivals=tuple(arrivals),
        surface_statistics=surface_statistics,
        rt60_s_by_band=rt60,
        direct_time_s=direct_time,
        total_ray_segments=total_segments,
        terminated_ray_count=terminated_rays,
        seed=settings.seed,
        bvh_statistics=intersection_statistics,
        research_status=(
            "Research geometric-acoustics estimate above the wave/geometric crossover; "
            "diffraction, phase interference, and source directivity are not modelled."
        ),
    )


__all__ = [
    "AcousticScene",
    "BVH",
    "BandMaterial",
    "Intersection",
    "PlaneSurface",
    "RayArrival",
    "RayTraceConfig",
    "RayTraceResult",
    "SurfaceStatistics",
    "TriangleSurface",
    "segment_sphere_intersection",
    "shoebox_scene",
    "trace_scene",
]

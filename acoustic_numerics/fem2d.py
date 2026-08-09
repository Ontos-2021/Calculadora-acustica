"""Sparse first-order triangular finite elements for two-dimensional room modes.

The rigid-wall problem solves ``K p = k**2 M p`` with consistent P1 element
mass matrices and natural Neumann boundaries.  Polygon meshes are generated with
SciPy Delaunay triangulation and filtered against the polygon; this is suitable
for simple research geometries (including L-shapes and trapezoids), but it is not
a production constrained-meshing replacement for geometries with tiny features
or holes.

Locally reacting, frequency-independent boundary impedances are represented by
the quadratic eigenproblem ``(k**2 M + i k C - K) p = 0`` under the
``exp(-i omega t)`` convention.  A callable impedance is handled by fixed-point
updates of that sparse quadratic problem.  These damped modes should be treated
as research estimates, not certified FEM results.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import inspect
import math
from typing import Callable, Mapping, Sequence, TypeAlias

import numpy as np
from scipy import linalg
from scipy.sparse import bmat, coo_matrix, csc_matrix, csr_matrix, eye
from scipy.sparse.linalg import ArpackNoConvergence, eigs, eigsh
from scipy.spatial import Delaunay, QhullError

from .finite_impedance import rt60_from_decay_rate


ArrayLike: TypeAlias = Sequence[Sequence[float]] | np.ndarray
BoundaryImpedanceValue: TypeAlias = complex | float | Callable[..., complex]
BoundaryImpedance: TypeAlias = BoundaryImpedanceValue | Mapping[int | str, BoundaryImpedanceValue]


@dataclass
class TriangularMesh:
    """A conforming P1 mesh and polygon-edge boundary markers."""

    nodes: np.ndarray
    elements: np.ndarray
    boundary_edges: np.ndarray
    boundary_markers: np.ndarray
    polygon: np.ndarray
    nominal_spacing_m: float

    def __post_init__(self) -> None:
        self.nodes = np.asarray(self.nodes, dtype=float)
        self.elements = np.asarray(self.elements, dtype=np.int64)
        self.boundary_edges = np.asarray(self.boundary_edges, dtype=np.int64)
        self.boundary_markers = np.asarray(self.boundary_markers, dtype=np.int64)
        self.polygon = np.asarray(self.polygon, dtype=float)
        if self.nodes.ndim != 2 or self.nodes.shape[1] != 2:
            raise ValueError("mesh nodes must have shape (N, 2)")
        if self.elements.ndim != 2 or self.elements.shape[1] != 3:
            raise ValueError("mesh elements must have shape (T, 3)")
        if len(self.nodes) < 3 or len(self.elements) < 1:
            raise ValueError("mesh must contain nodes and triangular elements")
        if self.boundary_edges.shape != (len(self.boundary_markers), 2):
            raise ValueError("boundary edge and marker counts differ")
        if np.min(self.elements) < 0 or np.max(self.elements) >= len(self.nodes):
            raise ValueError("element connectivity references an invalid node")
        if self.nominal_spacing_m <= 0.0:
            raise ValueError("nominal_spacing_m must be positive")


@dataclass(frozen=True)
class FEMMode:
    mode_index: int
    eigenvalue_per_m2: complex
    wavenumber_per_m: complex
    frequency_hz: float
    complex_frequency_hz: complex
    decay_rate_neper_s: float
    rt60_s: float
    shape: np.ndarray
    residual: float


@dataclass(frozen=True)
class FEMResult:
    mesh: TriangularMesh
    modes: tuple[FEMMode, ...]
    method: str
    boundary_condition: str
    research_status: str


@dataclass(frozen=True)
class CoupledMode:
    horizontal_mode_index: int
    vertical_order: int
    frequency_hz: float
    complex_frequency_hz: complex
    decay_rate_neper_s: float
    rt60_s: float


def _cross_2d(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def _polygon_array(vertices: ArrayLike) -> np.ndarray:
    polygon = np.asarray(vertices, dtype=float)
    if polygon.ndim != 2 or polygon.shape[1] != 2 or len(polygon) < 3:
        raise ValueError("polygon vertices must have shape (N, 2), N >= 3")
    if not np.all(np.isfinite(polygon)):
        raise ValueError("polygon vertices must be finite")
    if np.linalg.norm(polygon[0] - polygon[-1]) <= 1e-12:
        polygon = polygon[:-1]
    if len(polygon) < 3:
        raise ValueError("polygon must contain at least three distinct vertices")
    if any(np.linalg.norm(polygon[i] - polygon[(i + 1) % len(polygon)]) <= 1e-12 for i in range(len(polygon))):
        raise ValueError("polygon contains a zero-length edge")
    signed_twice_area = float(
        np.sum(polygon[:, 0] * np.roll(polygon[:, 1], -1))
        - np.sum(polygon[:, 1] * np.roll(polygon[:, 0], -1))
    )
    if abs(signed_twice_area) <= 1e-12:
        raise ValueError("polygon area must be positive")
    if signed_twice_area < 0.0:
        polygon = polygon[::-1].copy()
    for first_edge in range(len(polygon)):
        first_start = polygon[first_edge]
        first_end = polygon[(first_edge + 1) % len(polygon)]
        for second_edge in range(first_edge + 1, len(polygon)):
            if second_edge in {first_edge, (first_edge + 1) % len(polygon)}:
                continue
            if first_edge == 0 and second_edge == len(polygon) - 1:
                continue
            second_start = polygon[second_edge]
            second_end = polygon[(second_edge + 1) % len(polygon)]
            if _proper_segment_intersection(first_start, first_end, second_start, second_end):
                raise ValueError("polygon must be simple and non-self-intersecting")
    return polygon


def _point_segment_distance(point: np.ndarray, start: np.ndarray, end: np.ndarray) -> float:
    edge = end - start
    denominator = float(np.dot(edge, edge))
    if denominator == 0.0:
        return float(np.linalg.norm(point - start))
    t = float(np.clip(np.dot(point - start, edge) / denominator, 0.0, 1.0))
    return float(np.linalg.norm(point - (start + t * edge)))


def point_in_polygon(point: Sequence[float], vertices: ArrayLike, tolerance: float = 1e-10) -> bool:
    """Return whether a point is inside or on the boundary of a simple polygon."""

    polygon = np.asarray(vertices, dtype=float)
    p = np.asarray(point, dtype=float)
    if p.shape != (2,):
        raise ValueError("point must contain two coordinates")
    for i in range(len(polygon)):
        if _point_segment_distance(p, polygon[i], polygon[(i + 1) % len(polygon)]) <= tolerance:
            return True

    inside = False
    x, y = float(p[0]), float(p[1])
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if crossing_x > x:
                inside = not inside
        previous = current
    return inside


def _proper_segment_intersection(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> bool:
    def orientation(p: np.ndarray, q: np.ndarray, r: np.ndarray) -> float:
        return _cross_2d(q - p, r - p)

    o1 = orientation(a, b, c)
    o2 = orientation(a, b, d)
    o3 = orientation(c, d, a)
    o4 = orientation(c, d, b)
    tolerance = 1e-11
    return o1 * o2 < -tolerance and o3 * o4 < -tolerance


def _edge_crosses_polygon(start: np.ndarray, end: np.ndarray, polygon: np.ndarray) -> bool:
    for i in range(len(polygon)):
        edge_start = polygon[i]
        edge_end = polygon[(i + 1) % len(polygon)]
        if _proper_segment_intersection(start, end, edge_start, edge_end):
            return True
    return False


def _boundary_from_elements(
    nodes: np.ndarray,
    elements: np.ndarray,
    polygon: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    edge_counts: Counter[tuple[int, int]] = Counter()
    for element in elements:
        for first, second in ((element[0], element[1]), (element[1], element[2]), (element[2], element[0])):
            edge_counts[tuple(sorted((int(first), int(second))))] += 1
    boundary = np.asarray([edge for edge, count in edge_counts.items() if count == 1], dtype=np.int64)
    markers = np.empty(len(boundary), dtype=np.int64)
    for index, edge in enumerate(boundary):
        midpoint = 0.5 * (nodes[edge[0]] + nodes[edge[1]])
        distances = [
            _point_segment_distance(midpoint, polygon[i], polygon[(i + 1) % len(polygon)])
            for i in range(len(polygon))
        ]
        markers[index] = int(np.argmin(distances))
    return boundary, markers


def rectangle_mesh(width_m: float, height_m: float, nx: int = 21, ny: int = 21) -> TriangularMesh:
    """Create an exact structured triangular mesh of a rectangle."""

    if width_m <= 0.0 or height_m <= 0.0:
        raise ValueError("rectangle dimensions must be positive")
    if nx < 2 or ny < 2:
        raise ValueError("nx and ny must be at least 2")
    x_values = np.linspace(0.0, width_m, nx)
    y_values = np.linspace(0.0, height_m, ny)
    nodes = np.asarray([(x, y) for y in y_values for x in x_values], dtype=float)
    elements: list[tuple[int, int, int]] = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            lower_left = j * nx + i
            lower_right = lower_left + 1
            upper_left = lower_left + nx
            upper_right = upper_left + 1
            elements.append((lower_left, lower_right, upper_right))
            elements.append((lower_left, upper_right, upper_left))

    boundary_edges: list[tuple[int, int]] = []
    boundary_markers: list[int] = []
    # Polygon marker order: bottom, right, top, left.
    for i in range(nx - 1):
        boundary_edges.append((i, i + 1))
        boundary_markers.append(0)
    for j in range(ny - 1):
        boundary_edges.append((j * nx + nx - 1, (j + 1) * nx + nx - 1))
        boundary_markers.append(1)
    for i in range(nx - 1, 0, -1):
        boundary_edges.append(((ny - 1) * nx + i, (ny - 1) * nx + i - 1))
        boundary_markers.append(2)
    for j in range(ny - 1, 0, -1):
        boundary_edges.append((j * nx, (j - 1) * nx))
        boundary_markers.append(3)

    polygon = np.asarray([(0.0, 0.0), (width_m, 0.0), (width_m, height_m), (0.0, height_m)])
    return TriangularMesh(
        nodes=nodes,
        elements=np.asarray(elements, dtype=np.int64),
        boundary_edges=np.asarray(boundary_edges, dtype=np.int64),
        boundary_markers=np.asarray(boundary_markers, dtype=np.int64),
        polygon=polygon,
        nominal_spacing_m=max(width_m / (nx - 1), height_m / (ny - 1)),
    )


def polygon_mesh(vertices: ArrayLike, target_edge_length_m: float) -> TriangularMesh:
    """Generate and filter a Delaunay P1 mesh for a simple polygon.

    The routine preserves sampled polygon vertices in typical geometries, then
    removes triangles whose centroids/edges leave the domain.  Inspect the mesh
    for narrow or highly non-convex research geometries.
    """

    polygon = _polygon_array(vertices)
    if target_edge_length_m <= 0.0:
        raise ValueError("target_edge_length_m must be positive")

    minimum = np.min(polygon, axis=0)
    maximum = np.max(polygon, axis=0)
    extent = maximum - minimum
    if np.any(extent <= 0.0):
        raise ValueError("polygon must span both coordinate axes")

    boundary_points: list[np.ndarray] = []
    for index in range(len(polygon)):
        start = polygon[index]
        end = polygon[(index + 1) % len(polygon)]
        edge_length = float(np.linalg.norm(end - start))
        subdivisions = max(1, int(math.ceil(edge_length / target_edge_length_m)))
        boundary_points.extend(start + (end - start) * (step / subdivisions) for step in range(subdivisions))

    x_values = np.arange(minimum[0], maximum[0] + 0.5 * target_edge_length_m, target_edge_length_m)
    y_values = np.arange(minimum[1], maximum[1] + 0.5 * target_edge_length_m, target_edge_length_m)
    interior_points = [
        np.asarray((x, y), dtype=float)
        for y in y_values
        for x in x_values
        if point_in_polygon((x, y), polygon)
    ]
    points = np.asarray(boundary_points + interior_points, dtype=float)
    points = np.unique(np.round(points, decimals=12), axis=0)
    if len(points) < 3:
        raise ValueError("target spacing produced too few polygon mesh points")

    try:
        triangulation = Delaunay(points)
    except QhullError as exc:
        raise ValueError("polygon triangulation failed; inspect duplicate or collinear vertices") from exc

    accepted: list[np.ndarray] = []
    sample_fractions = (0.25, 0.5, 0.75)
    for simplex in triangulation.simplices:
        triangle = points[simplex]
        signed_area = _cross_2d(triangle[1] - triangle[0], triangle[2] - triangle[0])
        if abs(signed_area) <= 1e-14:
            continue
        if not point_in_polygon(np.mean(triangle, axis=0), polygon):
            continue
        valid = True
        for first, second in ((0, 1), (1, 2), (2, 0)):
            start = triangle[first]
            end = triangle[second]
            if _edge_crosses_polygon(start, end, polygon):
                valid = False
                break
            if any(not point_in_polygon(start + fraction * (end - start), polygon) for fraction in sample_fractions):
                valid = False
                break
        if not valid:
            continue
        ordered = simplex if signed_area > 0.0 else simplex[[0, 2, 1]]
        accepted.append(np.asarray(ordered, dtype=np.int64))

    if not accepted:
        raise ValueError("polygon filtering removed every triangle")
    elements = np.asarray(accepted, dtype=np.int64)
    used = np.unique(elements)
    index_map = np.full(len(points), -1, dtype=np.int64)
    index_map[used] = np.arange(len(used), dtype=np.int64)
    nodes = points[used]
    elements = index_map[elements]
    boundary_edges, boundary_markers = _boundary_from_elements(nodes, elements, polygon)
    return TriangularMesh(
        nodes=nodes,
        elements=elements,
        boundary_edges=boundary_edges,
        boundary_markers=boundary_markers,
        polygon=polygon,
        nominal_spacing_m=target_edge_length_m,
    )


def masked_rectangle_mesh(
    width_m: float,
    height_m: float,
    nx: int,
    ny: int,
    exclude_regions: Sequence[Mapping[str, float]],
) -> TriangularMesh:
    """Create a structured triangular approximation with rectangular cut-outs.

    Cut-out boundaries are grid-aligned/stair-stepped unless their coordinates
    coincide with grid lines.  This remains a P1 finite-element mesh; the
    approximation is explicitly exposed through ``nominal_spacing_m``.
    """

    base = rectangle_mesh(width_m, height_m, nx, ny)

    def excluded(point: np.ndarray) -> bool:
        for region in exclude_regions:
            x0, x1 = sorted((float(region["x0"]), float(region["x1"])))
            y0, y1 = sorted((float(region["y0"]), float(region["y1"])))
            tolerance = 1e-12
            if x0 + tolerance < point[0] < x1 - tolerance and y0 + tolerance < point[1] < y1 - tolerance:
                return True
        return False

    kept: list[np.ndarray] = []
    for element in base.elements:
        triangle = base.nodes[element]
        if excluded(np.mean(triangle, axis=0)) or any(excluded(vertex) for vertex in triangle):
            continue
        kept.append(element)
    if not kept:
        raise ValueError("exclude_regions removed the entire mesh")
    elements = np.asarray(kept, dtype=np.int64)
    used = np.unique(elements)
    index_map = np.full(len(base.nodes), -1, dtype=np.int64)
    index_map[used] = np.arange(len(used), dtype=np.int64)
    nodes = base.nodes[used]
    elements = index_map[elements]
    boundary_edges, boundary_markers = _boundary_from_elements(nodes, elements, base.polygon)
    return TriangularMesh(
        nodes=nodes,
        elements=elements,
        boundary_edges=boundary_edges,
        boundary_markers=boundary_markers,
        polygon=base.polygon,
        nominal_spacing_m=base.nominal_spacing_m,
    )


def assemble_matrices(mesh: TriangularMesh) -> tuple[csr_matrix, csr_matrix]:
    """Assemble sparse stiffness and consistent mass matrices."""

    rows: list[int] = []
    columns: list[int] = []
    stiffness_values: list[float] = []
    mass_values: list[float] = []
    reference_mass = np.asarray([[2.0, 1.0, 1.0], [1.0, 2.0, 1.0], [1.0, 1.0, 2.0]])

    for element in mesh.elements:
        coordinates = mesh.nodes[element]
        twice_area = _cross_2d(coordinates[1] - coordinates[0], coordinates[2] - coordinates[0])
        area = 0.5 * abs(twice_area)
        if area <= 1e-15:
            raise ValueError("mesh contains a degenerate triangle")
        b = np.asarray(
            [coordinates[1, 1] - coordinates[2, 1], coordinates[2, 1] - coordinates[0, 1], coordinates[0, 1] - coordinates[1, 1]]
        )
        c = np.asarray(
            [coordinates[2, 0] - coordinates[1, 0], coordinates[0, 0] - coordinates[2, 0], coordinates[1, 0] - coordinates[0, 0]]
        )
        local_stiffness = (np.outer(b, b) + np.outer(c, c)) / (4.0 * area)
        local_mass = area * reference_mass / 12.0
        for local_row, global_row in enumerate(element):
            for local_column, global_column in enumerate(element):
                rows.append(int(global_row))
                columns.append(int(global_column))
                stiffness_values.append(float(local_stiffness[local_row, local_column]))
                mass_values.append(float(local_mass[local_row, local_column]))

    shape = (len(mesh.nodes), len(mesh.nodes))
    stiffness = coo_matrix((stiffness_values, (rows, columns)), shape=shape).tocsr()
    mass = coo_matrix((mass_values, (rows, columns)), shape=shape).tocsr()
    return stiffness, mass


def _normalize_mode(shape: np.ndarray, mass: csr_matrix) -> np.ndarray:
    normalized = np.asarray(shape, dtype=complex).copy()
    norm_squared = float(np.real(np.vdot(normalized, mass @ normalized)))
    if norm_squared <= 0.0:
        raise ValueError("eigensolver returned a zero-mass mode")
    normalized /= math.sqrt(norm_squared)
    pivot = int(np.argmax(np.abs(normalized)))
    if abs(normalized[pivot]) > 0.0:
        normalized *= np.exp(-1j * np.angle(normalized[pivot]))
    return normalized


def _rigid_modes(
    stiffness: csr_matrix,
    mass: csr_matrix,
    num_modes: int,
    sound_speed_m_s: float,
) -> list[FEMMode]:
    node_count = stiffness.shape[0]
    requested = min(node_count - 1, max(num_modes + 3, 3))
    if requested < 2:
        raise ValueError("mesh is too small for modal analysis")
    if node_count <= 12 or requested >= node_count - 1:
        eigenvalues, eigenvectors = linalg.eigh(stiffness.toarray(), mass.toarray())
    else:
        eigenvalues, eigenvectors = eigsh(
            stiffness,
            k=requested,
            M=mass,
            sigma=-1e-9,
            which="LM",
            tol=1e-10,
        )
    order = np.argsort(np.real(eigenvalues))
    eigenvalues = np.real(eigenvalues[order])
    eigenvectors = eigenvectors[:, order]
    positive_tolerance = max(1e-9, 1e-10 * float(np.max(np.abs(eigenvalues))))
    selected = [index for index, value in enumerate(eigenvalues) if value > positive_tolerance][:num_modes]
    if len(selected) < num_modes:
        raise RuntimeError(f"only {len(selected)} non-zero eigenpairs were found")

    modes: list[FEMMode] = []
    for mode_number, eigen_index in enumerate(selected, start=1):
        eigenvalue = float(eigenvalues[eigen_index])
        shape = _normalize_mode(eigenvectors[:, eigen_index], mass)
        residual_vector = stiffness @ shape - eigenvalue * (mass @ shape)
        denominator = np.linalg.norm(stiffness @ shape) + eigenvalue * np.linalg.norm(mass @ shape)
        residual = float(np.linalg.norm(residual_vector) / max(denominator, np.finfo(float).eps))
        wavenumber = math.sqrt(eigenvalue)
        frequency = sound_speed_m_s * wavenumber / (2.0 * math.pi)
        modes.append(
            FEMMode(
                mode_index=mode_number,
                eigenvalue_per_m2=complex(eigenvalue),
                wavenumber_per_m=complex(wavenumber),
                frequency_hz=frequency,
                complex_frequency_hz=complex(frequency),
                decay_rate_neper_s=0.0,
                rt60_s=math.inf,
                shape=shape,
                residual=residual,
            )
        )
    return modes


def _select_boundary_value(
    boundary_impedance: BoundaryImpedance,
    marker: int,
) -> BoundaryImpedanceValue:
    if isinstance(boundary_impedance, Mapping):
        if marker in boundary_impedance:
            return boundary_impedance[marker]
        if str(marker) in boundary_impedance:
            return boundary_impedance[str(marker)]
        if "default" in boundary_impedance:
            return boundary_impedance["default"]
        return math.inf
    return boundary_impedance


def _evaluate_boundary_impedance(
    value: BoundaryImpedanceValue,
    frequency_hz: complex,
    marker: int,
    midpoint: np.ndarray,
) -> complex:
    if not callable(value):
        result = complex(value)
    else:
        try:
            signature = inspect.signature(value)
            positional = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind in (parameter.POSITIONAL_ONLY, parameter.POSITIONAL_OR_KEYWORD)
            ]
            has_varargs = any(parameter.kind == parameter.VAR_POSITIONAL for parameter in signature.parameters.values())
            argument_count = 3 if has_varargs else len(positional)
        except (TypeError, ValueError):
            argument_count = 1
        if argument_count >= 3:
            result = complex(value(frequency_hz, marker, midpoint.copy()))
        elif argument_count == 2:
            result = complex(value(frequency_hz, marker))
        else:
            result = complex(value(frequency_hz))
    if result == 0.0 or math.isnan(result.real) or math.isnan(result.imag):
        raise ValueError("boundary impedance must be finite or infinite and non-zero")
    return result


def assemble_boundary_admittance(
    mesh: TriangularMesh,
    boundary_impedance: BoundaryImpedance,
    frequency_hz: complex,
    *,
    density_kg_m3: float = 1.2,
    sound_speed_m_s: float = 343.0,
) -> csr_matrix:
    """Assemble ``C = integral (rho c / Z) N_i N_j ds`` on the boundary."""

    rows: list[int] = []
    columns: list[int] = []
    values: list[complex] = []
    for edge, marker_value in zip(mesh.boundary_edges, mesh.boundary_markers, strict=True):
        marker = int(marker_value)
        midpoint = 0.5 * (mesh.nodes[edge[0]] + mesh.nodes[edge[1]])
        impedance_value = _select_boundary_value(boundary_impedance, marker)
        impedance = _evaluate_boundary_impedance(impedance_value, frequency_hz, marker, midpoint)
        normalized_admittance = 0.0j if math.isinf(abs(impedance)) else density_kg_m3 * sound_speed_m_s / impedance
        if normalized_admittance == 0.0:
            continue
        length = float(np.linalg.norm(mesh.nodes[edge[1]] - mesh.nodes[edge[0]]))
        local = normalized_admittance * length * np.asarray([[2.0, 1.0], [1.0, 2.0]]) / 6.0
        for local_row, global_row in enumerate(edge):
            for local_column, global_column in enumerate(edge):
                rows.append(int(global_row))
                columns.append(int(global_column))
                values.append(complex(local[local_row, local_column]))
    return coo_matrix((values, (rows, columns)), shape=(len(mesh.nodes), len(mesh.nodes)), dtype=complex).tocsr()


def _quadratic_mode(
    stiffness: csr_matrix,
    mass: csr_matrix,
    boundary_matrix: csr_matrix,
    initial_wavenumber: complex,
) -> tuple[complex, np.ndarray]:
    node_count = stiffness.shape[0]
    zero = csr_matrix((node_count, node_count), dtype=complex)
    identity = eye(node_count, format="csr", dtype=complex)
    system_a = bmat([[zero, identity], [stiffness.astype(complex), -1j * boundary_matrix]], format="csc")
    system_b = bmat([[identity, zero], [zero, mass.astype(complex)]], format="csc")
    requested = min(8, 2 * node_count - 2)

    try:
        eigenvalues, eigenvectors = eigs(
            system_a,
            k=requested,
            M=system_b,
            sigma=initial_wavenumber,
            which="LM",
            tol=1e-9,
            maxiter=max(1000, 10 * node_count),
        )
    except ArpackNoConvergence as exc:
        if exc.eigenvalues is None or len(exc.eigenvalues) == 0:
            raise RuntimeError("impedance quadratic eigensolver did not converge") from exc
        eigenvalues = exc.eigenvalues
        eigenvectors = exc.eigenvectors

    candidates = [index for index, value in enumerate(eigenvalues) if value.real > 0.0]
    if not candidates:
        raise RuntimeError("impedance quadratic eigensolver returned no positive-wavenumber mode")

    def candidate_score(index: int) -> tuple[float, float]:
        value = complex(eigenvalues[index])
        growth_penalty = max(0.0, value.imag) * 100.0
        return (abs(value - initial_wavenumber) + growth_penalty, abs(value.imag))

    selected = min(candidates, key=candidate_score)
    return complex(eigenvalues[selected]), np.asarray(eigenvectors[:node_count, selected], dtype=complex)


def _impedance_modes(
    mesh: TriangularMesh,
    stiffness: csr_matrix,
    mass: csr_matrix,
    rigid_modes: Sequence[FEMMode],
    boundary_impedance: BoundaryImpedance,
    density_kg_m3: float,
    sound_speed_m_s: float,
) -> list[FEMMode]:
    solved: list[FEMMode] = []
    for rigid_mode in rigid_modes:
        wavenumber = rigid_mode.wavenumber_per_m
        shape = rigid_mode.shape
        boundary_matrix = csr_matrix(stiffness.shape, dtype=complex)
        for _ in range(12):
            frequency = sound_speed_m_s * wavenumber / (2.0 * math.pi)
            boundary_matrix = assemble_boundary_admittance(
                mesh,
                boundary_impedance,
                frequency,
                density_kg_m3=density_kg_m3,
                sound_speed_m_s=sound_speed_m_s,
            )
            updated_wavenumber, updated_shape = _quadratic_mode(
                stiffness,
                mass,
                boundary_matrix,
                wavenumber,
            )
            relative_change = abs(updated_wavenumber - wavenumber) / max(abs(wavenumber), 1e-12)
            wavenumber, shape = updated_wavenumber, updated_shape
            if relative_change <= 1e-8:
                break

        shape = _normalize_mode(shape, mass)
        polynomial_residual = (
            (wavenumber * wavenumber) * (mass @ shape)
            + 1j * wavenumber * (boundary_matrix @ shape)
            - stiffness @ shape
        )
        denominator = (
            abs(wavenumber * wavenumber) * np.linalg.norm(mass @ shape)
            + abs(wavenumber) * np.linalg.norm(boundary_matrix @ shape)
            + np.linalg.norm(stiffness @ shape)
        )
        residual = float(np.linalg.norm(polynomial_residual) / max(denominator, np.finfo(float).eps))
        complex_frequency = sound_speed_m_s * wavenumber / (2.0 * math.pi)
        decay_rate = max(0.0, float(-sound_speed_m_s * wavenumber.imag))
        solved.append(
            FEMMode(
                mode_index=rigid_mode.mode_index,
                eigenvalue_per_m2=wavenumber * wavenumber,
                wavenumber_per_m=wavenumber,
                frequency_hz=float(complex_frequency.real),
                complex_frequency_hz=complex(complex_frequency),
                decay_rate_neper_s=decay_rate,
                rt60_s=rt60_from_decay_rate(decay_rate),
                shape=shape,
                residual=residual,
            )
        )
    solved.sort(key=lambda mode: mode.frequency_hz)
    return [
        FEMMode(
            mode_index=index,
            eigenvalue_per_m2=mode.eigenvalue_per_m2,
            wavenumber_per_m=mode.wavenumber_per_m,
            frequency_hz=mode.frequency_hz,
            complex_frequency_hz=mode.complex_frequency_hz,
            decay_rate_neper_s=mode.decay_rate_neper_s,
            rt60_s=mode.rt60_s,
            shape=mode.shape,
            residual=mode.residual,
        )
        for index, mode in enumerate(solved, start=1)
    ]


def solve_fem_modes(
    mesh: TriangularMesh,
    num_modes: int = 5,
    *,
    sound_speed_m_s: float = 343.0,
    density_kg_m3: float = 1.2,
    boundary_impedance: BoundaryImpedance | None = None,
) -> FEMResult:
    """Solve the lowest non-constant acoustic modes on a triangular mesh."""

    if num_modes < 1:
        raise ValueError("num_modes must be at least 1")
    if sound_speed_m_s <= 0.0 or density_kg_m3 <= 0.0:
        raise ValueError("sound speed and density must be positive")
    stiffness, mass = assemble_matrices(mesh)
    rigid_modes = _rigid_modes(stiffness, mass, num_modes, sound_speed_m_s)
    if boundary_impedance is None:
        modes = rigid_modes
        boundary_condition = "rigid (natural Neumann)"
    else:
        modes = _impedance_modes(
            mesh,
            stiffness,
            mass,
            rigid_modes,
            boundary_impedance,
            density_kg_m3,
            sound_speed_m_s,
        )
        boundary_condition = "locally reacting impedance (sparse quadratic eigenproblem)"
    return FEMResult(
        mesh=mesh,
        modes=tuple(modes),
        method="P1 triangular finite element generalized eigenproblem",
        boundary_condition=boundary_condition,
        research_status=(
            "Research implementation. Validate mesh convergence; the built-in polygon mesher "
            "is not intended for holes, tiny features, or production certification."
        ),
    )


def solve_polygon_modes(
    vertices: ArrayLike,
    target_edge_length_m: float,
    num_modes: int = 5,
    **solver_options: object,
) -> FEMResult:
    """Convenience wrapper that meshes a polygon and solves its lowest modes."""

    return solve_fem_modes(
        polygon_mesh(vertices, target_edge_length_m),
        num_modes=num_modes,
        **solver_options,
    )


def couple_vertical_modes(
    horizontal_modes: Sequence[FEMMode | complex | float],
    height_m: float,
    max_vertical_order: int,
    *,
    sound_speed_m_s: float = 343.0,
) -> list[CoupledMode]:
    """Combine 2D horizontal modes with analytic rigid vertical modes.

    The separable estimate is ``f = sqrt(f_horizontal**2 + (n c / 2H)**2)``.
    It is exact only for an extruded domain with uniform rigid top and bottom.
    """

    if height_m <= 0.0 or sound_speed_m_s <= 0.0:
        raise ValueError("height and sound speed must be positive")
    if max_vertical_order < 0:
        raise ValueError("max_vertical_order must be non-negative")
    coupled: list[CoupledMode] = []
    for horizontal_index, horizontal_mode in enumerate(horizontal_modes, start=1):
        if isinstance(horizontal_mode, FEMMode):
            horizontal_frequency = horizontal_mode.complex_frequency_hz
            mode_index = horizontal_mode.mode_index
        else:
            horizontal_frequency = complex(horizontal_mode)
            mode_index = horizontal_index
        for vertical_order in range(max_vertical_order + 1):
            vertical_frequency = vertical_order * sound_speed_m_s / (2.0 * height_m)
            combined = complex(np.sqrt(horizontal_frequency * horizontal_frequency + vertical_frequency**2))
            if combined.real < 0.0 or (combined.real == 0.0 and combined.imag > 0.0):
                combined = -combined
            decay_rate = max(0.0, float(-2.0 * math.pi * combined.imag))
            coupled.append(
                CoupledMode(
                    horizontal_mode_index=mode_index,
                    vertical_order=vertical_order,
                    frequency_hz=float(combined.real),
                    complex_frequency_hz=combined,
                    decay_rate_neper_s=decay_rate,
                    rt60_s=rt60_from_decay_rate(decay_rate),
                )
            )
    coupled.sort(key=lambda mode: mode.frequency_hz)
    return coupled


__all__ = [
    "BoundaryImpedance",
    "CoupledMode",
    "FEMMode",
    "FEMResult",
    "TriangularMesh",
    "assemble_boundary_admittance",
    "assemble_matrices",
    "couple_vertical_modes",
    "masked_rectangle_mesh",
    "point_in_polygon",
    "polygon_mesh",
    "rectangle_mesh",
    "solve_fem_modes",
    "solve_polygon_modes",
]

import math
from .models import BANDAS_OCTAVA

C = 343.0


def _mesh_grid(width: float, height: float, nx: int, ny: int) -> tuple[list[float], list[float], int, int]:
    dx = width / (nx - 1) if nx > 1 else width
    dy = height / (ny - 1) if ny > 1 else height
    xs = [i * dx for i in range(nx)]
    ys = [j * dy for j in range(ny)]
    return xs, ys, nx, ny


def _laplacian_2d(nx: int, ny: int) -> list[list[float]]:
    n = nx * ny
    A = [[0.0] * n for _ in range(n)]
    for j in range(ny):
        for i in range(nx):
            idx = j * nx + i
            A[idx][idx] = -4.0
            if i > 0:
                A[idx][idx - 1] = 1.0
            if i < nx - 1:
                A[idx][idx + 1] = 1.0
            if j > 0:
                A[idx][idx - nx] = 1.0
            if j < ny - 1:
                A[idx][idx + nx] = 1.0
    return A


def _is_in_room(x: float, y: float, width: float, height: float, exclude: list[dict] | None = None) -> bool:
    if not (0 <= x <= width and 0 <= y <= height):
        return False
    if exclude:
        for rect in exclude:
            x0, y0, x1, y1 = rect["x0"], rect["y0"], rect["x1"], rect["y1"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return False
    return True


def _power_iteration(A: list[list[float]], n: int, max_iter: int = 100) -> tuple[float, list[float]]:
    v = [1.0 / math.sqrt(n)] * n
    lam = 0.0
    for _ in range(max_iter):
        w = [0.0] * n
        for i in range(n):
            s = 0.0
            for j in range(n):
                s += A[i][j] * v[j]
            w[i] = s
        lam_new = sum(v[i] * w[i] for i in range(n))
        w_norm = math.sqrt(sum(x * x for x in w))
        if w_norm < 1e-15:
            break
        v = [x / w_norm for x in w]
        if abs(lam_new - lam) < 1e-8:
            lam = lam_new
            break
        lam = lam_new
    return lam, v


def _deflate(A: list[list[float]], v: list[float], n: int) -> list[list[float]]:
    B = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            B[i][j] = A[i][j] - lam_shift * v[i] * v[j] if lam_shift > 0 else 0
    return B


lam_shift = 0.0


def compute_2d_modes(
    width: float,
    height: float,
    grid_nx: int = 20,
    grid_ny: int = 20,
    num_modes: int = 5,
    exclude_regions: list[dict] | None = None,
) -> list[dict]:
    xs, ys, nx, ny = _mesh_grid(width, height, grid_nx, grid_ny)
    interior_indices = []
    for j in range(ny):
        for i in range(nx):
            if _is_in_room(xs[i], ys[j], width, height, exclude_regions):
                interior_indices.append(j * nx + i)

    n_int = len(interior_indices)
    if n_int < 4:
        return []

    A = _laplacian_2d(nx, ny)
    A_int = [[A[i][j] for j in interior_indices] for i in interior_indices]

    modes = []
    global lam_shift
    lam_shift = 0.0
    for m in range(min(num_modes, n_int - 1)):
        lam, v = _power_iteration(A_int, n_int)
        if lam >= 0:
            break
        f_hz = C / (2 * math.pi) * math.sqrt(-lam) / max(width / (nx - 1), height / (ny - 1))

        A_int = _deflate(A_int, v, n_int)
        lam_shift = lam

        shape = []
        for j in range(ny):
            row = []
            for i in range(nx):
                idx = j * nx + i
                if idx in interior_indices:
                    vi = v[interior_indices.index(idx)]
                    row.append(round(vi, 4))
                else:
                    row.append(0.0)
            shape.append(row)

        modes.append({
            "mode": m + 1,
            "frequency_hz": round(abs(f_hz), 2),
            "shape_2d": shape,
            "grid_x": [round(x, 3) for x in xs],
            "grid_y": [round(y, 3) for y in ys],
        })
    return modes

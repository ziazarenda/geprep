"""Run with plain Python: python tests/uv_overlap.py (needs only numpy)."""

import importlib.util
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "uv_overlap",
    ROOT / "geprep" / "operations" / "uv_overlap.py",
)
overlap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(overlap)


def check(condition, message):
    if not condition:
        raise AssertionError(message)

    print("PASS:", message)


def quad_mesh(rects):
    """Axis-aligned UV quads. Returns uv, triangles, triangle_polygons."""
    uv, starts = [], []

    for u0, v0, u1, v1 in rects:
        starts.append(len(uv))
        uv.extend([(u0, v0), (u1, v0), (u1, v1), (u0, v1)])

    triangles, polygons = overlap.fan_triangles(starts, [4] * len(rects))

    return np.array(uv, float), triangles, polygons


# ---- fan_triangles ---------------------------------------------------------
loops, polys = overlap.fan_triangles([0, 3, 7], [3, 4, 5])
check(
    loops.tolist() == [
        [0, 1, 2],
        [3, 4, 5], [3, 5, 6],
        [7, 8, 9], [7, 9, 10], [7, 10, 11],
    ]
    and polys.tolist() == [0, 1, 1, 2, 2, 2],
    "fan_triangles splits triangle, quad and pentagon correctly",
)
check(
    overlap.fan_triangles([], [])[0].shape == (0, 3),
    "fan_triangles handles an empty mesh",
)

# ---- coverage and overlap on simple layouts -------------------------------
uv, tri, poly = quad_mesh([(0, 0, 1, 1)])
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
check(abs(coverage - 1.0) < 1e-3 and over == [], "full-tile quad: 100%, no overlap")

grid = [
    (x / 4, z / 4, (x + 1) / 4, (z + 1) / 4)
    for x in range(4) for z in range(4)
]
uv, tri, poly = quad_mesh(grid)
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
check(
    abs(coverage - 1.0) < 1e-3 and over == [],
    "16 touching quads: no false overlap along shared edges or diagonals",
)

uv, tri, poly = quad_mesh([(0, 0, 0.5, 0.5)])
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
check(abs(coverage - 0.25) < 5e-3 and over == [], "quarter-tile quad: 25%")

uv, tri, poly = quad_mesh([(0, 0, 0.5, 0.5), (0.25, 0.25, 0.75, 0.75), (0.8, 0.8, 0.9, 0.9)])
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
check(over == [0, 1], "two overlapping quads are flagged, the separate one is not")
check(
    abs(coverage - (0.25 + 0.25 - 0.0625 + 0.01)) < 5e-3,
    "coverage counts the overlap area only once",
)

uv, tri, poly = quad_mesh([(0, 0, 0.5, 1), (0, 0, 0.5, 1)])
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
check(over == [0, 1] and abs(coverage - 0.5) < 5e-3, "identical stacked islands overlap")

uv, tri, poly = quad_mesh([(0.5, 0.5, 1.5, 1.5)])
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
check(abs(coverage - 0.25) < 5e-3, "only the part inside the tile counts")

uv, tri, poly = quad_mesh([(1.2, 0.2, 1.8, 0.8), (-0.9, -0.9, -0.2, -0.2)])
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
check(coverage == 0.0 and over == [], "islands outside the tile are ignored")

uv, tri, poly = quad_mesh([(0.1, 0.1, 0.6, 0.6), (0.4, 0.4, 0.9, 0.9)])
flipped = uv.copy()
flipped[:, 0] = 1 - flipped[:, 0]
c1, o1 = overlap.measure_tile_coverage(uv, tri, poly)
c2, o2 = overlap.measure_tile_coverage(flipped, tri[:, ::-1], poly)
check(o1 == o2 == [0, 1], "overlap is found with either triangle winding")

check(
    overlap.measure_tile_coverage(np.zeros((0, 2)), np.zeros((0, 3), int), [])
    == (0.0, []),
    "empty mesh gives 0% and nothing flagged",
)

# ---- concave face: a fan can spill outside the shape ----------------------
L = np.array([(0, 0), (1, 0), (1, .5), (.5, .5), (.5, 1), (0, 1)], float)
good = [(0, 1, 2), (0, 2, 3), (0, 3, 5), (3, 4, 5)]  # a valid triangulation
island = [(0.62, 0.62), (0.9, 0.62), (0.9, 0.9), (0.62, 0.9)]
fan_wrong = 0

for shift in range(6):
    uv = np.vstack((np.roll(L, -shift, axis=0), island))
    proper = np.array([[(i - shift) % 6 for i in t] for t in good] + [(6, 7, 8), (6, 8, 9)])
    owners = [0] * 4 + [1, 1]
    coverage, over = overlap.measure_tile_coverage(uv, proper, owners)
    check(
        over == [] and abs(coverage - (0.75 + 0.28 ** 2)) < 5e-3,
        f"concave L with a separate island in its notch: correct (first loop {shift})",
    )
    fan, _ = overlap.fan_triangles([0], [6])
    _, fan_over = overlap.measure_tile_coverage(
        uv, np.vstack((fan, [(6, 7, 8), (6, 8, 9)])), [0] * len(fan) + [1, 1],
    )
    fan_wrong += bool(fan_over)

check(fan_wrong > 0, "regression guard: a plain fan really does misreport this shape")

# ---- must match a slow brute-force rasterizer exactly ---------------------
def brute(uv, triangles, resolution):
    hits = set()

    for t, loops in enumerate(triangles):
        (ax, ay), (bx, by), (cx, cy) = uv[loops] * resolution
        area = (bx - ax) * (cy - ay) - (cx - ax) * (by - ay)

        if abs(area) <= 1e-12:
            continue

        sign = 1 if area > 0 else -1

        for row in range(resolution):
            for column in range(resolution):
                px = column + 0.5 + overlap._JITTER_X
                py = row + 0.5 + overlap._JITTER_Y
                w0 = ((bx - px) * (cy - py) - (cx - px) * (by - py)) * sign
                w1 = ((cx - px) * (ay - py) - (ax - px) * (cy - py)) * sign
                w2 = ((ax - px) * (by - py) - (bx - px) * (ay - py)) * sign

                if w0 >= 0 and w1 >= 0 and w2 >= 0:
                    hits.add((row * resolution + column, t))

    return hits


rng = np.random.default_rng(11)

for trial in range(12):
    count = int(rng.integers(3, 12))
    uv = rng.uniform(-0.3, 1.3, size=(count * 3, 2))
    triangles = np.arange(count * 3).reshape(count, 3)

    for resolution in (32, 48):
        cells, owners = overlap.rasterize_triangles(uv, triangles, resolution)
        fast = set(zip(cells.tolist(), owners.tolist()))

        if fast != brute(uv, triangles, resolution):
            raise AssertionError(
                f"rasterizer differs from brute force (trial {trial}, "
                f"resolution {resolution})"
            )

print("PASS: matches the brute-force rasterizer on 24 random triangle sets")

# ---- large triangles and many small ones ---------------------------------
uv = np.array([[-5.0, -5.0], [6.0, -5.0], [0.5, 7.0]])
cells, owners = overlap.rasterize_triangles(uv, np.array([[0, 1, 2]]), 64)
check(len(cells) == 64 * 64, "a huge triangle covers the whole clipped tile")

# ---- speed ----------------------------------------------------------------
side = 220
rects = [
    (x / side, z / side, (x + 1) / side, (z + 1) / side)
    for x in range(side) for z in range(side)
]
uv, tri, poly = quad_mesh(rects)
start = time.time()
coverage, over = overlap.measure_tile_coverage(uv, tri, poly)
elapsed = time.time() - start
check(
    over == [] and coverage > 0.99,
    f"{side * side} quads ({len(tri)} triangles) cover the tile with no false "
    f"overlap ({elapsed:.2f}s)",
)

print("ALL UV OVERLAP TESTS PASSED")

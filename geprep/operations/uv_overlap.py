"""Estimate UV tile coverage and overlapping faces (pure numpy).

The 0-1 tile is sampled on a grid. Every sample point is tested against
every UV triangle, so overlaps smaller than a grid cell can be missed.
"""

import numpy as np

COVERAGE_RESOLUTION = 512

# Sample points are nudged by a fraction of a cell so that they almost
# never fall exactly on a shared edge, which would count twice.
_JITTER_X = 0.0137
_JITTER_Y = 0.0071

_BUCKET_SIZES = (4, 8, 16, 32, 64, 128, 256, 512)
_MAX_SAMPLES_PER_CHUNK = 2_000_000


def fan_triangles(loop_start, loop_total):
    """Split polygons into triangle fans.

    Returns (triangle_loops, triangle_polygons): the three loop indices of
    every triangle and the polygon each triangle came from.
    """
    loop_start = np.asarray(loop_start, dtype=np.int64)
    loop_total = np.asarray(loop_total, dtype=np.int64)
    counts = np.maximum(loop_total - 2, 0)

    polygons = np.repeat(np.arange(len(loop_start)), counts)
    first = np.cumsum(counts) - counts
    step = np.arange(len(polygons)) - np.repeat(first, counts)

    base = loop_start[polygons]
    loops = np.stack((base, base + step + 1, base + step + 2), axis=1)

    return loops, polygons


def rasterize_triangles(uv, triangles, resolution=COVERAGE_RESOLUTION):
    """Find which grid cells every triangle covers inside the 0-1 tile.

    Returns (cell_ids, triangle_ids), two arrays of the same length:
    cell_ids = row * resolution + column.
    """
    uv = np.asarray(uv, dtype=float)
    triangles = np.asarray(triangles, dtype=np.int64)
    corners = uv[triangles] * resolution
    x, y = corners[..., 0], corners[..., 1]

    area = (
        (x[:, 1] - x[:, 0]) * (y[:, 2] - y[:, 0])
        - (x[:, 2] - x[:, 0]) * (y[:, 1] - y[:, 0])
    )

    first_x = np.clip(np.floor(x.min(axis=1)), 0, resolution - 1).astype(int)
    last_x = np.clip(np.floor(x.max(axis=1)), 0, resolution - 1).astype(int)
    first_y = np.clip(np.floor(y.min(axis=1)), 0, resolution - 1).astype(int)
    last_y = np.clip(np.floor(y.max(axis=1)), 0, resolution - 1).astype(int)

    # Triangles fully outside the tile collapse onto an edge cell; they are
    # discarded by the inside test later, but skip the obvious ones now.
    inside_tile = (
        (x.max(axis=1) >= 0) & (x.min(axis=1) < resolution)
        & (y.max(axis=1) >= 0) & (y.min(axis=1) < resolution)
    )
    usable = (np.abs(area) > 1e-12) & inside_tile & np.isfinite(area)

    size = np.maximum(last_x - first_x, last_y - first_y) + 1
    cells, owners = [], []

    lower = 0

    for bucket in _BUCKET_SIZES:
        members = np.nonzero(usable & (size > lower) & (size <= bucket))[0]
        lower = bucket

        if not len(members):
            continue

        chunk = max(1, _MAX_SAMPLES_PER_CHUNK // (bucket * bucket))
        offsets = np.arange(bucket)

        for begin in range(0, len(members), chunk):
            ids = members[begin:begin + chunk]
            columns = first_x[ids, None] + offsets[None, :]
            rows = first_y[ids, None] + offsets[None, :]

            sample_x = (columns + 0.5 + _JITTER_X)[:, None, :]
            sample_y = (rows + 0.5 + _JITTER_Y)[:, :, None]

            x0, x1, x2 = (x[ids, k][:, None, None] for k in range(3))
            y0, y1, y2 = (y[ids, k][:, None, None] for k in range(3))
            sign = np.sign(area[ids])[:, None, None]

            w0 = ((x1 - sample_x) * (y2 - sample_y)
                  - (x2 - sample_x) * (y1 - sample_y)) * sign
            w1 = ((x2 - sample_x) * (y0 - sample_y)
                  - (x0 - sample_x) * (y2 - sample_y)) * sign
            w2 = ((x0 - sample_x) * (y1 - sample_y)
                  - (x1 - sample_x) * (y0 - sample_y)) * sign

            hit = (
                (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
                & (columns <= last_x[ids, None])[:, None, :]
                & (rows <= last_y[ids, None])[:, :, None]
                # Cells outside the tile belong to clipped triangles only.
                & (sample_x >= 0) & (sample_x < resolution)
                & (sample_y >= 0) & (sample_y < resolution)
            )

            local, row, column = np.nonzero(hit)
            cells.append(
                (first_y[ids][local] + row) * resolution
                + first_x[ids][local] + column
            )
            owners.append(ids[local])

    if not cells:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

    return np.concatenate(cells), np.concatenate(owners)


def measure_tile_coverage(
    uv,
    triangles,
    triangle_polygons,
    resolution=COVERAGE_RESOLUTION,
):
    """Return (coverage, overlapping_polygons).

    `coverage` is the share of the 0-1 tile covered by any face (0 to 1).
    `overlapping_polygons` is a sorted list of polygon indices that share
    at least one grid cell with another triangle.
    """
    if not len(triangles):
        return 0.0, []

    cells, owners = rasterize_triangles(uv, triangles, resolution)

    if not len(cells):
        return 0.0, []

    counts = np.bincount(cells, minlength=resolution * resolution)
    coverage = float(np.count_nonzero(counts)) / (resolution * resolution)

    shared = counts[cells] > 1
    polygons = np.unique(
        np.asarray(triangle_polygons)[owners[shared]]
    )

    return coverage, polygons.tolist()

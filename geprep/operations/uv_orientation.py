"""Rotate flat UV islands to a chosen direction (no Blender import needed)."""

import math

import numpy as np

# (action, button label, tooltip)
ORIENTATION_ACTIONS = (
    ("UP", "↑", "Point the cyan +U arrow up"),
    ("LEFT", "←", "Point the cyan +U arrow left"),
    (
        "ALIGN",
        "●",
        "Point +U right and +V up. Mirrored islands need Fix Mirroring first",
    ),
    ("RIGHT", "→", "Point the cyan +U arrow right"),
    ("DOWN", "↓", "Point the cyan +U arrow down"),
)

# Flips mirrored islands without rotating them.
MIRROR_ACTION = (
    "MIRROR",
    "Fix Mirroring",
    "Flip mirrored islands so +V points the right way. Does not rotate",
)

# (reference, label, tooltip)
ORIENTATION_REFERENCES = (
    (
        "AUTO",
        "Auto",
        "Use world Z as up, or world Y on horizontal surfaces",
    ),
    ("X", "World X", "Up points toward world +X along the surface"),
    ("Y", "World Y", "Up points toward world +Y along the surface"),
    ("Z", "World Z", "Up points toward world +Z along the surface"),
)

_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}

# Where +U should point on the surface, as (right, up).
_DESIRED_DIRECTION = {
    "MIRROR": (1, 0),
    "ALIGN": (1, 0),
    "RIGHT": (1, 0),
    "LEFT": (-1, 0),
    "UP": (0, 1),
    "DOWN": (0, -1),
}

# Strictest limits, used when the Flatness Tolerance is 0.
_FLAT_DOT = 0.99999
_FLAT_DISTANCE = 1e-5
_STRETCH_FRACTION = 1e-4
_SKEW_FRACTION = 1e-4
_UV_JOIN_DISTANCE = 1e-6


def flatness_limits(tolerance=0.0):
    """Return the flatness limits for a tolerance given in radians.

    0 keeps the strict limits (flat islands only). Larger values let an
    island bend by about that much and still be rotated by its average
    direction.
    """
    tolerance = max(0.0, float(tolerance))

    return {
        "normal_dot": min(_FLAT_DOT, math.cos(tolerance)),
        "plane_distance": max(_FLAT_DISTANCE, 0.5 * math.sin(tolerance)),
        "stretch": max(_STRETCH_FRACTION, tolerance * tolerance / 2),
        "skew": max(_SKEW_FRACTION, tolerance),
    }


def surface_orientation_axes(normal, reference="AUTO"):
    """Return the (right, up) world directions along a surface."""
    normal = np.asarray(normal, dtype=float)

    if not np.all(np.isfinite(normal)):
        raise ValueError(
            "The face normal contains invalid numbers. Run Mesh Checks"
        )

    length = np.linalg.norm(normal)

    if length <= 1e-20:
        raise ValueError(
            "The face has no normal direction. Run Mesh Checks"
        )

    if reference not in {"AUTO", "X", "Y", "Z"}:
        raise ValueError(f"Unknown Up Axis: {reference}")

    normal = normal / length

    def projected(key):
        axis = np.eye(3)[_AXIS_INDEX[key]]
        return axis - normal * (axis @ normal)

    up = projected("Z" if reference == "AUTO" else reference)

    if np.linalg.norm(up) < 1e-4:
        if reference != "AUTO":
            raise ValueError(
                f"World {reference} points through this face. "
                "Choose another Up Axis or Auto"
            )

        up = projected("Y")

    up /= np.linalg.norm(up)

    return np.cross(up, normal), up


def _uv_to_surface_matrix(uv, points, stretch=_STRETCH_FRACTION):
    """Fit the 2x2 matrix that maps centred UVs onto centred surface points.

    Row 0 is where +U goes on the surface and row 1 is where +V goes.
    """
    centered_uv = uv - uv.mean(axis=0)
    centered_points = points - points.mean(axis=0)

    matrix, _, rank, _ = np.linalg.lstsq(
        centered_uv,
        centered_points,
        rcond=None,
    )

    if rank == 0:
        raise ValueError("All UV points overlap. Unwrap this island again")

    if rank < 2:
        raise ValueError(
            "The UV points form a line. Unwrap this island again"
        )

    if abs(np.linalg.det(matrix)) < 1e-20:
        mesh_rank = np.linalg.matrix_rank(centered_points)

        if mesh_rank == 0:
            raise ValueError("All mesh points overlap. Run Mesh Checks")

        if mesh_rank < 2:
            raise ValueError(
                "The mesh points form a line. Run Mesh Checks"
            )

        raise ValueError(
            "The UVs do not give a usable surface direction. "
            "Unwrap this island again"
        )

    error = centered_uv @ matrix - centered_points
    extent = np.linalg.norm(np.ptp(points, axis=0))

    if np.max(np.linalg.norm(error, axis=1)) > max(extent * stretch, 1e-9):
        raise ValueError(
            "The UV island is stretched unevenly. "
            "Unwrap it again before aligning"
        )

    return matrix


def orient_uv_coordinates(coordinates, surface_points, action, tolerance=0.0):
    """Rotate one island's UVs, or flip it when `action` is MIRROR.

    `coordinates` are in texture pixels and `surface_points` are the
    matching points on the surface as (right, up) in world units.
    `tolerance` is the Flatness Tolerance in radians.
    """
    if action not in _DESIRED_DIRECTION:
        raise ValueError(f"Unknown orientation action: {action}")

    limits = flatness_limits(tolerance)
    uv = np.asarray(coordinates, dtype=float)
    points = np.asarray(surface_points, dtype=float)

    if not np.all(np.isfinite(uv)):
        raise ValueError("The UV map contains invalid coordinates")

    if not np.all(np.isfinite(points)):
        raise ValueError(
            "The mesh contains invalid coordinates. Run Mesh Checks"
        )

    center = (uv.min(axis=0) + uv.max(axis=0)) * 0.5
    local = uv - center
    matrix = _uv_to_surface_matrix(local, points, limits["stretch"])
    mirrored = np.linalg.det(matrix) < 0

    if action == "MIRROR":
        if not mirrored:
            return uv.copy()

        local[:, 1] *= -1

        return local + center

    if action == "ALIGN" and mirrored:
        raise ValueError(
            "The island is mirrored. Use Fix Mirroring first"
        )

    desired = np.array(_DESIRED_DIRECTION[action], dtype=float)
    perpendicular = np.array((-desired[1], desired[0]))
    u_axis, v_axis = matrix

    angle = math.atan2(u_axis @ perpendicular, v_axis @ perpendicular)
    direction = u_axis * math.cos(angle) - v_axis * math.sin(angle)

    if direction @ desired < 0:
        angle += math.pi

    c, s = math.cos(angle), math.sin(angle)
    rotated = local @ np.array(((c, s), (-s, c)))

    if action == "ALIGN":
        aligned = _uv_to_surface_matrix(rotated, points, limits["stretch"])

        if abs(aligned[1, 0]) > np.linalg.norm(aligned[1]) * limits["skew"]:
            raise ValueError(
                "The UVs are skewed. Unwrap them again to align both arrows"
            )

    output = rotated + center

    if not np.all(np.isfinite(output)):
        raise ValueError(
            "Aligning produced invalid UV coordinates. Check the unwrap"
        )

    return output


def _uv_close(first, second):
    return math.hypot(
        first[0] - second[0],
        first[1] - second[1],
    ) <= _UV_JOIN_DISTANCE


def _loops_share_uv_edge(loop, other, layer):
    """Return whether two loops on one edge have the same UVs."""
    following = loop.link_loop_next
    uv_start = tuple(loop[layer].uv)
    uv_end = tuple(following[layer].uv)

    if other.vert == loop.vert:
        other_start = tuple(other[layer].uv)
        other_end = tuple(other.link_loop_next[layer].uv)

    else:
        other_start = tuple(other.link_loop_next[layer].uv)
        other_end = tuple(other[layer].uv)

    return _uv_close(uv_start, other_start) and _uv_close(uv_end, other_end)


def find_selected_uv_islands(bm, layer):
    """Return the UV islands that contain a selected, visible face.

    Starts from the selected faces and spreads across edges whose UVs
    match, so faces of other islands are never visited.
    """
    visited = set()
    islands = []

    for start in bm.faces:
        if start in visited or start.hide or not start.select:
            continue

        island = [start]
        visited.add(start)
        pending = [start]

        while pending:
            face = pending.pop()

            for loop in face.loops:
                for other in loop.edge.link_loops:
                    neighbour = other.face

                    if neighbour in visited:
                        continue

                    if _loops_share_uv_edge(loop, other, layer):
                        visited.add(neighbour)
                        island.append(neighbour)
                        pending.append(neighbour)

        islands.append(island)

    return islands


def face_normal_sums(positions, counts):
    """Return each face's normal scaled by twice its area.

    `positions` holds the corners of all faces one after another and
    `counts` says how many corners each face has. Uses Newell's method,
    so the whole island is handled in a few numpy calls.
    """
    counts = np.asarray(counts)
    starts = np.concatenate(([0], np.cumsum(counts)[:-1]))
    following = np.arange(len(positions)) + 1
    following[starts + counts - 1] = starts

    crosses = np.cross(positions, positions[following])

    return np.add.reduceat(crosses, starts, axis=0)


def plan_uv_orientation(
    obj,
    bm,
    uv_name,
    size,
    action,
    reference="AUTO",
    tolerance=0.0,
):
    """Calculate the UV changes for every island with a selected face.

    Returns (changes, changed_islands, selected_islands). Each change is
    (loop_uv_data, old_uv, new_uv). Nothing is modified here.
    `tolerance` is the Flatness Tolerance in radians.
    """
    layer = bm.loops.layers.uv.get(uv_name) if uv_name else None

    if layer is None:
        raise ValueError(
            f"UV map {uv_name!r} is missing"
            if uv_name
            else "This mesh has no UV map"
        )

    limits = flatness_limits(tolerance)
    selected = find_selected_uv_islands(bm, layer)
    matrix = obj.matrix_world
    changes = []
    changed_islands = 0

    for island in selected:
        loops = [loop for face in island for loop in face.loops]

        problems = []

        if any(loop[layer].pin_uv for loop in loops):
            problems.append("The island has pinned UV points. Unpin them first")

        if any(face.hide for face in island):
            problems.append("The island includes hidden faces. Show them first")

        if problems:
            raise ValueError("; ".join(problems))

        corner_points = {}
        rows = []

        for loop in loops:
            vert = loop.vert
            point = corner_points.get(vert)

            if point is None:
                point = corner_points[vert] = tuple(matrix @ vert.co)

            rows.append(point)

        positions = np.array(rows, dtype=float)
        positions -= positions.mean(axis=0)

        normal_sums = face_normal_sums(
            positions,
            [len(face.loops) for face in island],
        )
        lengths = np.linalg.norm(normal_sums, axis=1)

        if np.any(lengths <= 1e-20):
            raise ValueError(
                "A face in this island has no area. Run Mesh Checks"
            )

        # The average normal is weighted by face area.
        average = normal_sums.sum(axis=0)
        average_length = np.linalg.norm(average)

        if average_length <= 1e-20:
            raise ValueError("The island folds back on itself")

        normal = average / average_length

        if np.any(
            (normal_sums / lengths[:, None]) @ normal < limits["normal_dot"]
        ):
            raise ValueError(
                "The island bends too much. Split it into flatter islands "
                "or raise the Flatness Tolerance"
            )

        right, up = surface_orientation_axes(normal, reference)

        plane_limit = max(
            np.linalg.norm(np.ptp(positions, axis=0))
            * limits["plane_distance"],
            1e-9,
        )

        if np.max(np.abs(positions @ normal)) > plane_limit:
            raise ValueError(
                "The island is not flat enough. "
                "Raise the Flatness Tolerance or split it"
            )

        uv = np.array([tuple(loop[layer].uv) for loop in loops]) * size
        surface = np.column_stack((positions @ right, positions @ up))
        planned = orient_uv_coordinates(uv, surface, action, tolerance) / size

        if action == "MIRROR" and np.array_equal(planned, uv / size):
            continue

        changed_islands += 1
        changes.extend(
            (loop[layer], tuple(loop[layer].uv), tuple(value))
            for loop, value in zip(loops, planned)
        )

    return changes, changed_islands, len(selected)

"""Run with plain Python: python tests/uv_orientation_math.py

Tests the Orient UVs math and island planning with a tiny fake edit-mesh,
so no Blender is needed. Only numpy is required.
"""

import importlib.util
import math
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "uv_orientation",
    ROOT / "geprep" / "operations" / "uv_orientation.py",
)
orientation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(orientation)

DIRECTION_ACTIONS = ("UP", "LEFT", "RIGHT", "DOWN")
WANTED = {
    "ALIGN": (1, 0), "RIGHT": (1, 0), "LEFT": (-1, 0),
    "UP": (0, 1), "DOWN": (0, -1),
}


def check(condition, message):
    if not condition:
        raise AssertionError(message)

    print("PASS:", message)


def expect_error(function, text, message):
    try:
        function()

    except ValueError as error:
        check(text in str(error), f"{message} ({error})")
        return

    raise AssertionError(f"{message}: no error was raised")


def fit(uv, points):
    centered = uv - uv.mean(axis=0)
    return np.linalg.lstsq(
        centered, points - points.mean(axis=0), rcond=None,
    )[0]


def direction_of(out, surface):
    u_axis = fit(out, surface)[0]
    return u_axis / np.linalg.norm(u_axis)


# ---- pure math -----------------------------------------------------------
surface = np.array([[0, 0], [2, 0], [2, 1], [0, 1]], dtype=float)
size = np.array([1024.0, 512.0])

for mirrored in (False, True):
    for angle in (0.0, 0.7, 2.4, -1.9):
        uv = (surface / 4 + 0.3) * size

        if mirrored:
            uv[:, 1] = size[1] * 0.9 - uv[:, 1]

        c, s = math.cos(angle), math.sin(angle)
        centre = uv.mean(axis=0)
        uv = (uv - centre) @ np.array(((c, s), (-s, c))) + centre
        det_before = np.linalg.det(fit(uv, surface))

        check(
            (det_before < 0) == mirrored,
            f"test island mirrored={mirrored} has the expected handedness",
        )

        for action in DIRECTION_ACTIONS:
            out = orientation.orient_uv_coordinates(uv, surface, action)
            check(
                np.allclose(direction_of(out, surface), WANTED[action], atol=1e-6),
                f"{action}: +U correct (mirrored={mirrored}, angle={angle:+.1f})",
            )
            check(
                np.sign(np.linalg.det(fit(out, surface))) == np.sign(det_before),
                f"{action}: mirroring kept",
            )

        if mirrored:
            expect_error(
                lambda: orientation.orient_uv_coordinates(uv, surface, "ALIGN"),
                "Fix Mirroring",
                "ALIGN refuses a mirrored island",
            )

            fixed = orientation.orient_uv_coordinates(uv, surface, "MIRROR")
            check(
                np.linalg.det(fit(fixed, surface)) > 0,
                "MIRROR fixes a mirrored island",
            )
            check(
                np.allclose(
                    direction_of(fixed, surface),
                    direction_of(uv, surface),
                    atol=1e-6,
                ),
                "MIRROR does not rotate the island",
            )
            check(
                np.allclose(fixed.min(axis=0), uv.min(axis=0))
                and np.allclose(fixed.max(axis=0), uv.max(axis=0)),
                "MIRROR keeps the island in the same place",
            )
            uv = fixed

        out = orientation.orient_uv_coordinates(uv, surface, "ALIGN")
        u_axis, v_axis = fit(out, surface)
        check(
            np.allclose(direction_of(out, surface), (1, 0), atol=1e-6)
            and np.linalg.det(fit(out, surface)) > 0
            and v_axis[1] > 0,
            f"ALIGN: +U right, +V up (mirrored={mirrored}, angle={angle:+.1f})",
        )

        if not mirrored:
            same = orientation.orient_uv_coordinates(uv, surface, "MIRROR")
            check(
                np.array_equal(same, uv),
                "MIRROR leaves a correct island exactly as it was",
            )

# face_normal_sums: triangle, quad and n-gon, offset far from the origin
tri = np.array([[0, 0, 0], [2, 0, 0], [0, 3, 0]], float)
quad = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]], float)
pent = np.array([[0, 0, 0], [2, 0, 0], [3, 1, 0], [1, 2, 0], [-1, 1, 0]], float)
shift = np.array([5.0, -3.0, 7.0])
points = np.vstack((tri, quad, pent)) + shift
sums = orientation.face_normal_sums(points - points.mean(axis=0), [3, 4, 5])
check(
    np.allclose(sums[:, :2], 0) and np.allclose(sums[:, 2], [6.0, 2.0, 10.0]),
    "face_normal_sums gives twice the area along +Z for tri, quad and n-gon",
)
rev = orientation.face_normal_sums(
    np.vstack((tri[::-1], quad[::-1], pent[::-1])) + shift - points.mean(axis=0),
    [3, 4, 5],
)
check(np.allclose(rev[:, 2], [-6.0, -2.0, -10.0]), "reversed winding flips the normal")

right, up = orientation.surface_orientation_axes((0, 0, 1), "AUTO")
check(
    np.allclose(right, (1, 0, 0)) and np.allclose(up, (0, 1, 0)),
    "AUTO on a floor uses world Y as up",
)
right, up = orientation.surface_orientation_axes((0, -1, 0), "AUTO")
check(np.allclose(up, (0, 0, 1)), "AUTO on a wall uses world Z as up")

expect_error(
    lambda: orientation.surface_orientation_axes((0, 0, 1), "Z"),
    "points through this face",
    "World Z on a floor is rejected",
)
expect_error(
    lambda: orientation.orient_uv_coordinates(
        [[0, 0], [1, 0], [2, 0]], [[0, 0], [1, 0], [2, 0]], "UP",
    ),
    "form a line",
    "collinear UVs are rejected",
)

limits = orientation.flatness_limits(0.0)
check(
    limits["normal_dot"] == 0.99999
    and limits["plane_distance"] == 1e-5
    and limits["stretch"] == 1e-4
    and limits["skew"] == 1e-4,
    "tolerance 0 keeps the original strict limits",
)
check(
    all(
        orientation.flatness_limits(math.radians(5))[key] >= limits[key]
        for key in ("plane_distance", "stretch", "skew")
    )
    and orientation.flatness_limits(math.radians(5))["normal_dot"]
    < limits["normal_dot"],
    "a larger tolerance loosens every limit",
)


# ---- fake edit-mesh --------------------------------------------------------
class Vec:
    def __init__(self, *values):
        self.v = np.array(values, dtype=float)

    def __iter__(self):
        return iter(self.v.tolist())


class Layer:
    pass


class LoopUV:
    def __init__(self, uv):
        self.uv = Vec(*uv)
        self.pin_uv = False


class Vert:
    def __init__(self, co):
        self.co = np.array(co, dtype=float)


class Face:
    def __init__(self):
        self.loops = []
        self.select = True
        self.hide = False


class Loop:
    def __init__(self, vert, face, uv):
        self.vert, self.face, self._uv = vert, face, LoopUV(uv)
        self.link_loop_next = None
        self.edge = None

    def __getitem__(self, layer):
        return self._uv


class Edge:
    def __init__(self):
        self.link_loops = []


class Matrix:
    def __matmul__(self, co):
        return np.asarray(co, dtype=float)


class Layers:
    def __init__(self, layer):
        self.uv = self
        self._layer = layer

    def get(self, name):
        return self._layer if name == "UVMap" else None


class Mesh:
    def __init__(self, layer):
        self.faces, self.edges = [], []
        self.loops = type("L", (), {})()
        self.loops.layers = Layers(layer)


class Obj:
    matrix_world = Matrix()


def build_mesh(positions, faces, uv_of):
    """positions: {key: xyz}; faces: [[key, ...]]; uv_of(face, corner)."""
    layer = Layer()
    bm = Mesh(layer)
    verts = {key: Vert(co) for key, co in positions.items()}
    edges = {}

    for face_index, keys in enumerate(faces):
        face = Face()
        face.loops = [
            Loop(verts[key], face, uv_of(face_index, corner))
            for corner, key in enumerate(keys)
        ]

        for corner, loop in enumerate(face.loops):
            loop.link_loop_next = face.loops[(corner + 1) % len(keys)]
            edge_key = frozenset((keys[corner], keys[(corner + 1) % len(keys)]))
            edge = edges.setdefault(edge_key, Edge())
            edge.link_loops.append(loop)
            loop.edge = edge

        bm.faces.append(face)

    bm.edges = list(edges.values())

    return bm, layer


def grid(nx, nz, uv_of):
    """A wall of quads facing +Y."""
    positions = {(x, z): (x, 0, z) for x in range(nx + 1) for z in range(nz + 1)}
    faces = [
        [(x, z), (x, z + 1), (x + 1, z + 1), (x + 1, z)]
        for x in range(nx)
        for z in range(nz)
    ]

    return build_mesh(positions, faces, uv_of)


def reference_islands(bm, layer):
    """The original whole-mesh union-find, kept to compare against."""
    parents = {face: face for face in bm.faces}

    def root(face):
        while parents[face] != face:
            parents[face] = parents[parents[face]]
            face = parents[face]

        return face

    def endpoints(loop):
        following = loop.link_loop_next

        return {
            loop.vert: tuple(loop[layer].uv),
            following.vert: tuple(following[layer].uv),
        }

    for edge in bm.edges:
        loops = list(edge.link_loops)

        for index, first in enumerate(loops):
            first_uv = endpoints(first)

            for second in loops[index + 1:]:
                second_uv = endpoints(second)

                if all(
                    math.hypot(
                        uv[0] - second_uv[vertex][0],
                        uv[1] - second_uv[vertex][1],
                    ) <= 1e-6
                    for vertex, uv in first_uv.items()
                ):
                    parents[root(first.face)] = root(second.face)

    groups = {}

    for face in bm.faces:
        groups.setdefault(root(face), []).append(face)

    return list(groups.values())


def as_sets(islands, bm):
    index = {face: i for i, face in enumerate(bm.faces)}

    return {frozenset(index[face] for face in island) for island in islands}


# ---- island finding: new flood fill must match the old union-find --------
rng = random.Random(7)

for trial in range(60):
    nx, nz = rng.randint(2, 7), rng.randint(2, 6)
    groups = [rng.randint(0, 2) for _ in range(nx * nz)]

    def uv_of(face_index, corner, groups=groups, nz=nz):
        x, z = divmod(face_index, nz)
        cx, cz = [(0, 0), (0, 1), (1, 1), (1, 0)][corner]
        offset = groups[face_index] * 0.37

        return ((x + cx) * 0.1 + offset, (z + cz) * 0.1 + offset * 0.5)

    bm, layer = grid(nx, nz, uv_of)

    for face in bm.faces:
        face.select = rng.random() < 0.25

        if rng.random() < 0.05:
            face.hide = True

    everything = reference_islands(bm, layer)
    wanted = [
        island for island in everything
        if any(face.select and not face.hide for face in island)
    ]
    found = orientation.find_selected_uv_islands(bm, layer)

    if as_sets(found, bm) != as_sets(wanted, bm):
        raise AssertionError(f"island mismatch in trial {trial}")

print("PASS: flood fill matches the old union-find on 60 random meshes")

bm, layer = grid(6, 6, lambda f, c: ((f // 6 + (c in (2, 3))) * 0.1,
                                    (f % 6 + (c in (1, 2))) * 0.1))
for face in bm.faces:
    face.select = False

bm.faces[0].select = True
visited_faces = orientation.find_selected_uv_islands(bm, layer)
check(
    len(visited_faces) == 1 and len(visited_faces[0]) == 36,
    "one selected face finds its whole connected island",
)


# ---- planning on a wall ----------------------------------------------------
def rotated_uv(face_index, corner):
    x, z = divmod(face_index, 1)[0], 0
    cx, cz = [(0, 0), (0, 1), (1, 1), (1, 0)][corner]
    angle = 0.9
    # Seen from +Y the wall's right is world -X, so U runs along -X.
    u, w = -(x + cx) * 0.25, (z + cz) * 0.25

    return (
        0.3 + u * math.cos(angle) - w * math.sin(angle),
        0.4 + u * math.sin(angle) + w * math.cos(angle),
    )


tile = np.array([1024.0, 1024.0])


def wall_surface(bm):
    loops = [lp for f in bm.faces for lp in f.loops]
    pos = np.array([lp.vert.co for lp in loops])
    # wall faces +Y: up = +Z and right = up x normal = world -X
    return loops, np.column_stack((-pos[:, 0], pos[:, 2]))


for action in DIRECTION_ACTIONS + ("ALIGN",):
    bm, layer = grid(2, 1, rotated_uv)
    changes, changed, selected = orientation.plan_uv_orientation(
        Obj(), bm, "UVMap", tile, action, "AUTO",
    )
    check(
        changed == 1 and selected == 1 and len(changes) == 8,
        f"{action}: planned 1 island",
    )

    for data, old, new in changes:
        data.uv = Vec(*new)

    loops, surface_pts = wall_surface(bm)
    uv = np.array([tuple(lp[layer].uv) for lp in loops]) * tile
    check(
        np.allclose(direction_of(uv, surface_pts), WANTED[action], atol=1e-6),
        f"{action}: wall island ends up pointing the right way",
    )

# Fix Mirroring on a wall
bm, layer = grid(2, 1, lambda f, c: (
    lambda u, v: (u, 1 - v)
)(*rotated_uv(f, c)))
changes, changed, selected = orientation.plan_uv_orientation(
    Obj(), bm, "UVMap", tile, "MIRROR", "AUTO",
)
check(changed == 1 and selected == 1, "MIRROR plans a mirrored wall island")

bm, layer = grid(2, 1, rotated_uv)
changes, changed, selected = orientation.plan_uv_orientation(
    Obj(), bm, "UVMap", tile, "MIRROR", "AUTO",
)
check(
    changed == 0 and selected == 1 and not changes,
    "MIRROR skips islands that are not mirrored",
)

# no selection / pinned / missing map
bm, layer = grid(2, 1, rotated_uv)
for face in bm.faces:
    face.select = False

result = orientation.plan_uv_orientation(
    Obj(), bm, "UVMap", tile, "UP", "AUTO",
)
check(result == ([], 0, 0), "no selection plans nothing")

bm, layer = grid(2, 1, rotated_uv)
bm.faces[0].loops[0]._uv.pin_uv = True
expect_error(
    lambda: orientation.plan_uv_orientation(
        Obj(), bm, "UVMap", tile, "UP", "AUTO",
    ),
    "pinned",
    "pinned UVs are rejected",
)
expect_error(
    lambda: orientation.plan_uv_orientation(Obj(), bm, "", tile, "UP", "AUTO"),
    "no UV map",
    "missing UV map is rejected",
)


# ---- curved island: Flatness Tolerance ------------------------------------
def cylinder_strip(span_degrees, faces_count=6, radius=1.0, bottom=0.0):
    step = math.radians(span_degrees) / faces_count
    positions, faces = {}, []

    for i in range(faces_count + 1):
        angle = i * step
        for row, z in enumerate((bottom, bottom + 1.0)):
            positions[(i, row)] = (
                radius * math.cos(angle), radius * math.sin(angle), z,
            )

    for i in range(faces_count):
        faces.append([(i, 0), (i + 1, 0), (i + 1, 1), (i, 1)])

    def uv_of(face_index, corner):
        i = face_index + (1 if corner in (1, 2) else 0)
        row = 1 if corner in (2, 3) else 0
        u, v = radius * i * step, float(row)
        angle = 0.6
        return (
            0.2 + 0.4 * (u * math.cos(angle) - v * math.sin(angle)),
            0.3 + 0.4 * (u * math.sin(angle) + v * math.cos(angle)),
        )

    return build_mesh(positions, faces, uv_of)


def cylinder_direction(bm, layer, reference="AUTO"):
    loops = [lp for f in bm.faces for lp in f.loops]
    pos = np.array([lp.vert.co for lp in loops])
    counts = [len(f.loops) for f in bm.faces]
    average = orientation.face_normal_sums(pos, counts).sum(axis=0)
    right, up = orientation.surface_orientation_axes(
        average / np.linalg.norm(average), reference,
    )
    surface_pts = np.column_stack((pos @ right, pos @ up))
    uv = np.array([tuple(lp[layer].uv) for lp in loops]) * tile

    return direction_of(uv, surface_pts)


for span in (30, 60):
    bm, layer = cylinder_strip(span)
    expect_error(
        lambda: orientation.plan_uv_orientation(
            Obj(), bm, "UVMap", tile, "RIGHT", "AUTO",
        ),
        "bends too much",
        f"strict tolerance rejects a {span} degree strip",
    )

for span, tolerance_degrees in ((10, 6), (30, 16), (36, 19)):
    for action in DIRECTION_ACTIONS:
        bm, layer = cylinder_strip(span)
        changes, changed, selected = orientation.plan_uv_orientation(
            Obj(), bm, "UVMap", tile, action, "AUTO",
            math.radians(tolerance_degrees),
        )

        for data, old, new in changes:
            data.uv = Vec(*new)

        direction = cylinder_direction(bm, layer)
        error = math.degrees(math.acos(min(1.0, direction @ np.array(WANTED[action]))))
        check(
            changed == 1 and error < 1.0,
            f"{span} deg strip, tolerance {tolerance_degrees}: "
            f"{action} within {error:.2f} deg",
        )

bm, layer = cylinder_strip(180)
expect_error(
    lambda: orientation.plan_uv_orientation(
        Obj(), bm, "UVMap", tile, "RIGHT", "AUTO", math.radians(5),
    ),
    "bends too much",
    "a half cylinder is still rejected at a small tolerance",
)

print("ALL UV ORIENTATION TESTS PASSED")

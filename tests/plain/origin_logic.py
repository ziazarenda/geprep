"""Plain-Python tests for operations/origin.py (no Blender needed).

Run from the folder that contains the `geprep` package:
    python3 tests/origin_logic.py

Blender's Matrix and Vector are replaced by small numpy versions. Objects
follow Blender's rule  world = parent_world @ parent_inverse @ basis,
with  basis = Translation(location) @ rotation @ scale.
"""

import importlib.util
import os
import sys
import types
from types import SimpleNamespace

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "geprep")


# ---------------------------------------------------- Blender math stand-ins
class Vector:
    def __init__(self, values):
        self.v = np.array(list(values), dtype=float)

    def copy(self):
        return Vector(self.v)

    def __add__(self, other):
        return Vector(self.v + other.v)

    def __sub__(self, other):
        return Vector(self.v - other.v)

    def __neg__(self):
        return Vector(-self.v)

    def __iter__(self):
        return iter(self.v)

    def __getitem__(self, index):
        return self.v[index]


class Matrix:
    def __init__(self, rows):
        self.m = np.array(rows, dtype=float)

    @staticmethod
    def Translation(vector):
        m = np.eye(4)
        m[:3, 3] = vector.v
        return Matrix(m)

    def copy(self):
        return Matrix(self.m)

    def to_3x3(self):
        return Matrix(self.m[:3, :3])

    def inverted(self):
        try:
            return Matrix(np.linalg.inv(self.m))
        except np.linalg.LinAlgError:
            raise ValueError("Matrix cannot be inverted") from None

    def __matmul__(self, other):
        if isinstance(other, Matrix):
            return Matrix(self.m @ other.m)
        if self.m.shape == (4, 4):
            return Vector(self.m[:3, :3] @ other.v + self.m[:3, 3])
        return Vector(self.m @ other.v)


fake_mathutils = types.ModuleType("mathutils")
fake_mathutils.Matrix = Matrix
fake_mathutils.Vector = Vector
sys.modules["mathutils"] = fake_mathutils

for name in ("geprep", "geprep.helpers", "geprep.operations"):
    sys.modules[name] = types.ModuleType(name)
    sys.modules[name].__path__ = []


def load(module_name, relative_path):
    spec = importlib.util.spec_from_file_location(
        module_name,
        os.path.join(ROOT, relative_path),
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


load("geprep.helpers.objects", "helpers/objects.py")
og = load("geprep.operations.origin", "operations/origin.py")


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


# ------------------------------------------------------------ scene fakes
class Mesh:
    def __init__(self, coordinates, shape_key_coordinates=None):
        self.coordinates = np.array(coordinates, dtype=float)
        self.vertices = self
        self.users = 1
        self.use_fake_user = False
        self.is_editable = True
        self.animation_data = None
        self.updates = 0
        self.fail_on_update = None
        self.shape_keys = None
        if shape_key_coordinates is not None:
            self.shape_keys = SimpleNamespace(
                animation_data=None,
                coordinates=np.array(shape_key_coordinates, dtype=float),
            )

    def __len__(self):
        return len(self.coordinates)

    def foreach_get(self, attribute, buffer):
        assert attribute == "co"
        buffer[:] = type(buffer)("f", self.coordinates.flatten())

    def transform(self, matrix, shape_keys=False):
        def apply(points):
            return points @ matrix.m[:3, :3].T + matrix.m[:3, 3]

        self.coordinates = apply(self.coordinates)

        if shape_keys and self.shape_keys is not None:
            self.shape_keys.coordinates = apply(self.shape_keys.coordinates)

    def update(self):
        self.updates += 1

        if self.fail_on_update == self.updates:
            raise RuntimeError("injected failure")


REGISTRY = []


def rotation_z(degrees):
    c, s = np.cos(np.radians(degrees)), np.sin(np.radians(degrees))
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def rotation_x(degrees):
    c, s = np.cos(np.radians(degrees)), np.sin(np.radians(degrees))
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


class Obj:
    def __init__(self, name, mesh, location=(0, 0, 0), rotation=None,
                 scale=(1, 1, 1), parent=None, parent_inverse=None):
        self.name = name
        self.data = mesh
        self.location = Vector(location)
        self.rotation = np.eye(3) if rotation is None else rotation
        self.scale = np.array(scale, dtype=float)
        self.parent = parent
        self.parent_type = "OBJECT"
        self.matrix_parent_inverse = parent_inverse or Matrix(np.eye(4))
        self.modifiers = []
        self.constraints = []
        self.animation_data = None
        self.library = None
        self.override_library = None
        self.is_editable = True
        self.geprep_checker = SimpleNamespace(active=False)
        REGISTRY.append(self)

    @property
    def children(self):
        return [obj for obj in REGISTRY if obj.parent is self]

    @property
    def matrix_basis(self):
        m = np.eye(4)
        m[:3, :3] = self.rotation @ np.diag(self.scale)
        m[:3, 3] = self.location.v
        return Matrix(m)

    @property
    def matrix_world(self):
        local = self.matrix_parent_inverse @ self.matrix_basis
        if self.parent is None:
            return Matrix(np.eye(4)) @ self.matrix_basis
        return self.parent.matrix_world @ local

    def world_vertices(self):
        points = self.data.coordinates
        m = self.matrix_world.m
        return points @ m[:3, :3].T + m[:3, 3]


context = SimpleNamespace(view_layer=SimpleNamespace(update=lambda: None))

BOX = [(x, y, z) for x in (-1, 3) for y in (0, 4) for z in (-2, 6)]  # 8 corners
# bounds: x -1..3, y 0..4, z -2..6


def snapshot(objects):
    return [(obj.world_vertices().copy(), obj.matrix_world.m.copy()) for obj in objects]


def unchanged(before, objects, moved=(), tolerance=1e-9):
    """Vertices never move. Objects that were not moved keep their matrix too."""
    return all(
        np.allclose(points, obj.world_vertices(), atol=tolerance)
        and (obj in moved or np.allclose(world, obj.matrix_world.m, atol=tolerance))
        for (points, world), obj in zip(before, objects)
    )


# ------------------------------------------------------- bounds and tables
check(set(og.ORIGIN_FACTORS) | {"CURSOR"} == {key for key, _, _ in og.ORIGIN_POSITIONS},
      "Every origin position has a factor, and the cursor is the only extra")
check({key for key, _, _ in og.ORIGIN_DEPTHS} == set(og.DEPTH_FACTORS),
      "Every depth has a factor")
check(all(description for _, _, description in og.ORIGIN_POSITIONS + og.ORIGIN_DEPTHS),
      "Every button has a tooltip text")

low, high = (-1, 0, -2), (3, 4, 6)
expected_x = {"L": -1, "C": 1, "R": 3}
expected_z = {"B": -2, "C": 2, "T": 6}
for position in og.ORIGIN_FACTORS:
    vertical = "C" if position == "C" else position[0]
    horizontal = "C" if position == "C" else position[1]
    for depth, y in (("FRONT", 0.0), ("CENTER", 2.0), ("BACK", 4.0)):
        point = og.bounds_point(low, high, position, depth)
        assert point == (expected_x[horizontal], y, expected_z[vertical]), (position, depth, point)
check(True, "All 27 bounds points are at the expected spot (X left to right, Z bottom to top, Y front to back)")
check(og.bounds_point(low, high, "BC") == (1, 2, -2), "Depth defaults to the center")

mesh = Mesh(BOX)
check(tuple(og.local_bounds_point(mesh, "BC", "FRONT")) == (1, 0, -2),
      "Bounds are read from the mesh vertices")
def raises(function, text, *args):
    try:
        function(*args)
    except Exception as error:
        return text in str(error)
    return False


check(raises(og.local_bounds_point, "no vertices", Mesh(np.zeros((0, 3))), "C"),
      "A mesh without vertices is refused")

# ------------------------------------------------- moving: the main invariant
def move(objects, position, depth="CENTER", cursor=None):
    targets = og.origin_targets(
        objects, position, depth,
        Vector((0, 0, 0)) if cursor is None else cursor,
    )
    og.move_mesh_origins(context, targets)
    return targets


# 1. Plain object.
REGISTRY.clear()
plain = Obj("Plain", Mesh(BOX), location=(10, 20, 30))
before = snapshot([plain])
world_target = plain.matrix_world @ Vector((1, 0, -2))      # bottom center, front
move([plain], "BC", "FRONT")
check(unchanged(before, [plain], moved=[plain]), "A plain object: every vertex stays where it was")
check(np.allclose(plain.matrix_world.m[:3, 3], world_target.v),
      "A plain object: the origin is at the chosen point")
check(np.isclose(plain.data.coordinates[:, 2].min(), 0.0)
      and np.isclose(plain.data.coordinates[:, 1].min(), 0.0),
      "Bottom and front of the mesh now sit at the origin")

# 2. Rotated, non-uniformly scaled, parented with an odd parent inverse.
odd_inverse = Matrix(np.array([[1, 0, 0, 3], [0, 1, 0, -1], [0, 0, 1, 2], [0, 0, 0, 1.0]]))
for position in og.ORIGIN_FACTORS:
    for depth in ("FRONT", "CENTER", "BACK"):
        REGISTRY.clear()
        parent = Obj("Parent", Mesh(BOX), location=(1, -2, 0.5),
                     rotation=rotation_z(30) @ rotation_x(15), scale=(2, 1, 0.5))
        tilted = Obj("Tilted", Mesh(BOX), location=(4, 5, 6), rotation=rotation_z(-70) @ rotation_x(40),
                     scale=(0.5, 3, 1.5), parent=parent, parent_inverse=odd_inverse)
        objects = [parent, tilted]
        before = snapshot(objects)
        expected_origins = [
            (obj.matrix_world @ Vector(og.bounds_point(low, high, position, depth))).v
            for obj in objects
        ]
        move(objects, position, depth)
        assert unchanged(before, objects, moved=objects), (position, depth)
        assert all(np.allclose(obj.matrix_world.m[:3, 3], expected)
                   for obj, expected in zip(objects, expected_origins)), (position, depth)
check(True, "Rotated, scaled and parented objects: nothing moves and every origin lands "
            "on its point (all 9 positions x 3 depths)")

# 3. Children keep their world position, parent inverse or not.
REGISTRY.clear()
parent = Obj("Parent", Mesh(BOX), location=(2, 3, 4), rotation=rotation_z(25), scale=(1.5, 1.5, 1.5))
child_a = Obj("ChildA", Mesh(BOX), location=(1, 1, 1), parent=parent,
              parent_inverse=Matrix(np.eye(4)))
child_b = Obj("ChildB", Mesh(BOX), location=(0, 2, -1), rotation=rotation_x(33), scale=(1, 2, 3),
              parent=parent, parent_inverse=odd_inverse)
grandchild = Obj("Grandchild", Mesh(BOX), location=(5, 0, 0), parent=child_b,
                 parent_inverse=Matrix(np.eye(4)))
objects = [parent, child_a, child_b, grandchild]
before = snapshot(objects)
move([parent], "TR", "BACK")
check(unchanged(before, objects, moved=[parent]), "Children and grandchildren stay exactly where they were")

# 4. Parent and child both selected.
REGISTRY.clear()
parent = Obj("Parent", Mesh(BOX), location=(2, 3, 4), rotation=rotation_z(25), scale=(1.5, 1.5, 1.5))
child = Obj("Child", Mesh(BOX), location=(1, 1, 1), rotation=rotation_x(10), parent=parent,
            parent_inverse=odd_inverse)
before = snapshot([parent, child])
expected = [(parent.matrix_world @ Vector(og.bounds_point(low, high, "BL", "BACK"))).v,
            (child.matrix_world @ Vector(og.bounds_point(low, high, "BL", "BACK"))).v]
move([parent, child], "BL", "BACK")
check(unchanged(before, [parent, child], moved=[parent, child]), "Parent and child moved together: nothing shifts")
check(all(np.allclose(obj.matrix_world.m[:3, 3], e) for obj, e in zip([parent, child], expected)),
      "Parent and child both get their own origin")

# 5. 3D cursor.
REGISTRY.clear()
one = Obj("One", Mesh(BOX), location=(1, 2, 3), rotation=rotation_z(40), scale=(2, 2, 2))
two = Obj("Two", Mesh(BOX), location=(-5, 0, 1), scale=(1, 3, 1))
cursor = Vector((7, -3, 2))
before = snapshot([one, two])
move([one, two], "CURSOR", cursor=cursor)
check(unchanged(before, [one, two], moved=[one, two]), "Moving to the cursor leaves the geometry in place")
check(np.allclose(one.matrix_world.m[:3, 3], cursor.v) and np.allclose(two.matrix_world.m[:3, 3], cursor.v),
      "Every selected origin is placed at the cursor")

REGISTRY.clear()
flat = Obj("Flat", Mesh(BOX), scale=(1, 0, 1))
check(raises(og.origin_targets, "non-invertible", [flat], "CURSOR", "CENTER", Vector((0, 0, 0))),
      "A zero-scale object is refused for the cursor with a clear message")

# 6. Shape keys move with the mesh.
REGISTRY.clear()
keyed = Obj("Keyed", Mesh(BOX, shape_key_coordinates=np.array(BOX) * 1.5), location=(1, 1, 1))
key_before = keyed.data.shape_keys.coordinates.copy()
move([keyed], "BC", "CENTER")
check(np.allclose(keyed.data.shape_keys.coordinates, key_before - np.array([1, 2, -2])),
      "Shape keys are shifted together with the mesh")

# 7. Rollback.
REGISTRY.clear()
first = Obj("First", Mesh(BOX), location=(1, 2, 3), rotation=rotation_z(20))
second = Obj("Second", Mesh(BOX), location=(4, 5, 6), scale=(2, 2, 2))
kid = Obj("Kid", Mesh(BOX), location=(1, 0, 0), parent=first, parent_inverse=odd_inverse)
objects = [first, second, kid]
saved = [(obj.data.coordinates.copy(), obj.location.v.copy(), obj.matrix_parent_inverse.m.copy())
         for obj in objects]
before = snapshot(objects)
second.data.fail_on_update = 1
try:
    move([first, second], "TR", "FRONT")
    raise SystemExit("expected a failure")
except RuntimeError:
    pass
check(all(np.allclose(obj.data.coordinates, c) and np.allclose(obj.location.v, l)
          and np.allclose(obj.matrix_parent_inverse.m, p)
          for obj, (c, l, p) in zip(objects, saved)),
      "A failure part way through restores every mesh, location and parent inverse")
check(unchanged(before, objects), "...and the scene looks exactly as before, matrices included")


# ------------------------------------------------------------- blockers
def clean(name="Wall"):
    REGISTRY.clear()
    return Obj(name, Mesh(BOX))


def problems(obj):
    return " | ".join(og.origin_problems(obj))


check(og.origin_problems(clean()) == [], "A clean object has no problems")

obj = clean(); obj.geprep_checker.active = True
check("checker preview" in problems(obj), "An active checker blocks")
obj = clean(); obj.is_editable = False
check("cannot be edited" in problems(obj), "A read-only object blocks")
obj = clean(); obj.override_library = object()
check("library override" in problems(obj), "A library override blocks")
obj = clean(); obj.data.is_editable = False
check("mesh cannot be edited" in problems(obj), "A read-only mesh blocks")
obj = clean(); obj.data.users = 3
check("shared by 3 users" in problems(obj) and "single user" in problems(obj),
      "A shared mesh blocks and says how to fix it")
obj = clean(); obj.data.users, obj.data.use_fake_user = 2, True
check(og.origin_problems(obj) == [], "A fake user does not count as sharing")
obj = clean(); obj.modifiers = [
    SimpleNamespace(name="Mirror", show_viewport=True, show_render=True),
    SimpleNamespace(name="Off", show_viewport=False, show_render=False)]
check("turn off these modifiers" in problems(obj) and "Mirror" in problems(obj)
      and "Off" not in problems(obj),
      "Enabled modifiers block, ones that are off everywhere do not")
obj = clean(); obj.modifiers = [
    SimpleNamespace(name="RenderOnly", show_viewport=False, show_render=True)]
check("RenderOnly" in problems(obj), "A modifier that is only on for render blocks")
obj = clean(); obj.modifiers = [
    SimpleNamespace(name="ViewOnly", show_viewport=True, show_render=False)]
check("ViewOnly" in problems(obj), "A modifier that is only on in the viewport blocks")
obj = clean(); obj.constraints = [SimpleNamespace(name="Child Of")]
check("constraints: Child Of" in problems(obj), "Constraints block")
for where in ("object", "mesh", "keys"):
    obj = clean(); obj.data.shape_keys = SimpleNamespace(animation_data=None)
    action = SimpleNamespace(action=object(), drivers=[], nla_tracks=[])
    target = {"object": obj, "mesh": obj.data, "keys": obj.data.shape_keys}[where]
    target.animation_data = action
    check("animation or drivers" in problems(obj), f"Animation on the {where} blocks")
obj = clean(); obj.parent = Obj("Bone", Mesh(BOX)); obj.parent_type = "VERTEX"
check("vertex parenting" in problems(obj), "Vertex parenting on the object blocks")
obj = clean()
kid = Obj("Kid", Mesh(BOX), parent=obj); kid.parent_type = "BONE"
check("Child 'Kid' uses bone parenting" in problems(obj), "Non-object parenting on a child blocks")
kid.parent_type = "OBJECT"; kid.is_editable = False
check("Child 'Kid' cannot be edited" in problems(obj), "A read-only child blocks")
kid.is_editable = True; kid.library = object()
check("Child 'Kid' cannot be edited" in problems(obj), "A linked child blocks")
kid.library = None; kid.override_library = object()
check("Child 'Kid' is a library override" in problems(obj),
      "A library-override child blocks, even though it is editable")
kid.override_library = None
check(og.origin_problems(obj) == [], "A local, editable child is fine")

REGISTRY.clear()
many = [Obj(f"O{i}", Mesh(BOX)) for i in range(6)]
for item in many:
    item.data.users = 2
found = og.all_origin_problems(many)
check(len(found) == 6, "Problems of every selected object are collected")
text = og.summarize_problems(found)
check(text.count("shared by") == 4 and text.endswith("and 2 more"),
      "Only the first few problems are shown, with a count of the rest")
check(len(found) == 6, "Summarizing does not change the list")

print("ALL ORIGIN LOGIC TESTS PASSED")

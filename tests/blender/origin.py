# needs-window
exec("""
import itertools
import uuid

import bpy
from mathutils import Matrix, Vector


context = bpy.context
scene = context.scene
prefix = f"GEPrepOrg_{uuid.uuid4().hex[:6]}"
made_objects, made_meshes = [], []
saved_cursor = scene.cursor.location.copy()
saved_depth = scene.geprep.origin_depth

LOW, HIGH = (-1, 0, -2), (3, 4, 6)       # the bounds of every test box
FACTORS = {
    "TL": (0, 1), "TC": (0.5, 1), "TR": (1, 1),
    "CL": (0, 0.5), "C": (0.5, 0.5), "CR": (1, 0.5),
    "BL": (0, 0), "BC": (0.5, 0), "BR": (1, 0),
}
DEPTHS = {"FRONT": 0.0, "CENTER": 0.5, "BACK": 1.0}


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def make_box(name, location=(0, 0, 0), rotation=(0, 0, 0), scale=(1, 1, 1)):
    corners = [(x, y, z) for x in (LOW[0], HIGH[0]) for y in (LOW[1], HIGH[1])
               for z in (LOW[2], HIGH[2])]
    faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1),
             (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh = bpy.data.meshes.new(f"{prefix}_{name}")
    mesh.from_pydata(corners, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(f"{prefix}_{name}", mesh)
    scene.collection.objects.link(obj)
    obj.location = location
    obj.rotation_euler = rotation
    obj.scale = scale
    made_objects.append(obj)
    made_meshes.append(mesh)
    return obj


def adopt(child, parent):
    context.view_layer.update()
    child.parent = parent
    child.matrix_parent_inverse = parent.matrix_world.inverted()


def select(*objects):
    for item in list(context.selected_objects):
        item.select_set(False)
    for item in objects:
        item.select_set(True)
    context.view_layer.objects.active = objects[0]


def world_points(obj):
    context.view_layer.update()
    return [obj.matrix_world @ vertex.co for vertex in obj.data.vertices]


def same_points(first, second, tolerance=1e-4):
    return all((a - b).length < tolerance for a, b in zip(first, second))


def same_matrix(first, second, tolerance=1e-4):
    return all(abs(first[i][j] - second[i][j]) < tolerance
               for i in range(4) for j in range(4))


def local_point(position, depth):
    x_factor, z_factor = FACTORS[position]
    factors = (x_factor, DEPTHS[depth], z_factor)
    return Vector(tuple(low + (high - low) * f for low, high, f in zip(LOW, HIGH, factors)))


def current_point(obj, position, depth):
    # Same point, but from the mesh as it is now (not the original box).
    coords = [vertex.co for vertex in obj.data.vertices]
    low = [min(c[i] for c in coords) for i in range(3)]
    high = [max(c[i] for c in coords) for i in range(3)]
    x_factor, z_factor = FACTORS[position]
    factors = (x_factor, DEPTHS[depth], z_factor)
    return Vector(tuple(l + (h - l) * f for l, h, f in zip(low, high, factors)))


def origin_world(obj):
    return obj.matrix_world.translation.copy()


try:
    original_scene = context.window.scene

    # ---- every position and depth on a transformed object
    for position, depth in itertools.product(FACTORS, DEPTHS):
        obj = make_box(f"grid_{position}_{depth}", location=(10, 20, 30),
                       rotation=(0.3, 0.2, 0.5), scale=(2, 1, 0.5))
        context.view_layer.update()
        before = world_points(obj)
        expected = obj.matrix_world @ local_point(position, depth)
        select(obj)
        assert bpy.ops.geprep.set_origin(position=position, depth=depth) == {"FINISHED"}
        assert same_points(before, world_points(obj)), (position, depth, "geometry moved")
        assert (origin_world(obj) - expected).length < 1e-4, (position, depth, "origin misplaced")
    check(True, "All 9 positions x 3 depths: geometry stays put and the origin lands on its point")

    obj = make_box("bottom", location=(1, 2, 3), rotation=(0.1, 0.4, 0.9), scale=(1, 2, 3))
    select(obj)
    bpy.ops.geprep.set_origin(position="BC", depth="FRONT")
    zs = [v.co.z for v in obj.data.vertices]
    ys = [v.co.y for v in obj.data.vertices]
    check(abs(min(zs)) < 1e-5 and abs(min(ys)) < 1e-5,
          "After Bottom Center / Front the mesh bottom and front sit at the origin")

    # ---- hierarchy: children keep their world matrices
    parent = make_box("parent", location=(2, 3, 4), rotation=(0.2, 0.1, 0.7), scale=(1.5, 1.5, 1.5))
    child = make_box("child", location=(1, 1, 1), rotation=(0.5, 0, 0.2), scale=(1, 2, 3))
    grandchild = make_box("grand", location=(5, 0, 0))
    adopt(child, parent)
    adopt(grandchild, child)
    context.view_layer.update()
    family = [parent, child, grandchild]
    points = [world_points(o) for o in family]
    matrices = [o.matrix_world.copy() for o in family]
    select(parent)
    check(bpy.ops.geprep.set_origin(position="TR", depth="BACK") == {"FINISHED"},
          "Moving a parent's origin runs")
    check(all(same_points(p, world_points(o)) for p, o in zip(points, family)),
          "The parent, child and grandchild geometry all stay in place")
    check(same_matrix(matrices[1], child.matrix_world) and same_matrix(matrices[2], grandchild.matrix_world),
          "The children keep exactly the same world transform")

    # ---- parent and child both selected
    points = [world_points(o) for o in family]
    select(parent, child)
    expected = [o.matrix_world @ current_point(o, "BL", "BACK") for o in (parent, child)]
    bpy.ops.geprep.set_origin(position="BL", depth="BACK")
    check(all(same_points(p, world_points(o)) for p, o in zip(points, family)),
          "A parent and child moved together: no geometry shifts")
    check(all((origin_world(o) - e).length < 1e-4 for o, e in zip((parent, child), expected)),
          "Each of them gets its own origin")

    # ---- 3D cursor
    one = make_box("cursor_one", location=(1, 2, 3), rotation=(0.2, 0.3, 0.4), scale=(2, 2, 2))
    two = make_box("cursor_two", location=(-5, 0, 1), scale=(1, 3, 1))
    points = [world_points(o) for o in (one, two)]
    scene.cursor.location = (7, -3, 2)
    select(one, two)
    check(bpy.ops.geprep.set_origin(position="CURSOR") == {"FINISHED"}, "Origin to 3D Cursor runs")
    check(all(same_points(p, world_points(o)) for p, o in zip(points, (one, two))),
          "The cursor move leaves the geometry in place")
    check(all((origin_world(o) - Vector((7, -3, 2))).length < 1e-4 for o in (one, two)),
          "Every selected origin is at the cursor")
    scene.cursor.location = saved_cursor

    # ---- shape keys move with the mesh
    keyed = make_box("keyed", location=(1, 1, 1))
    keyed.shape_key_add(name="Basis")
    key = keyed.shape_key_add(name="Wide")
    for point in key.data:
        point.co.x *= 1.5
    before_key = [p.co.copy() for p in key.data]
    shift = local_point("BC", "CENTER")
    select(keyed)
    bpy.ops.geprep.set_origin(position="BC", depth="CENTER")
    check(all((p.co - (b - shift)).length < 1e-4 for p, b in zip(key.data, before_key)),
          "Shape key coordinates are shifted together with the mesh")

    # ---- things that must be refused
    def refused(obj, text, label, extra=()):
        clean = make_box(f"clean_for_{label}", location=(3, 3, 3))
        clean_points, own_points = world_points(clean), world_points(obj)
        own_matrix = obj.matrix_world.copy()
        select(obj, clean, *extra)
        try:
            bpy.ops.geprep.set_origin(position="BC")
            raise AssertionError(f"{label}: the operator should have refused")
        except RuntimeError as error:
            check(text in str(error), f"{label} is refused with a clear message")
        check(same_points(world_points(clean), clean_points)
              and same_points(world_points(obj), own_points)
              and same_matrix(obj.matrix_world, own_matrix),
              f"{label}: nothing was moved, not even the other selected object")

    shared = make_box("shared")
    twin = bpy.data.objects.new(f"{prefix}_twin", shared.data)
    scene.collection.objects.link(twin)
    made_objects.append(twin)
    refused(shared, "shared by 2 users", "A shared mesh")

    modded = make_box("modded")
    modded.modifiers.new("Bevel", "BEVEL")
    refused(modded, "turn off these modifiers", "An enabled modifier")
    render_only = make_box("render_only")
    hidden = render_only.modifiers.new("Bevel", "BEVEL")
    hidden.show_viewport = False
    hidden.show_render = True
    refused(render_only, "turn off these modifiers", "A render-only modifier")

    checked = make_box("checked")
    checked.geprep_checker.active = True
    try:
        refused(checked, "checker preview", "An active checker")
    finally:
        checked.geprep_checker.active = False

    animated = make_box("animated")
    animated.keyframe_insert("location", frame=1)
    refused(animated, "animation or drivers", "Animation")

    constrained = make_box("constrained")
    constrained.constraints.new("COPY_LOCATION")
    refused(constrained, "constraints", "A constraint")

    # ---- the depth setting is stored in the scene
    check(scene.geprep.origin_depth in {"FRONT", "CENTER", "BACK"}, "The depth setting exists")

    check(context.window.scene == original_scene, "The scene is unchanged")
    print("ALL ORIGIN TESTS PASSED")

finally:
    scene.cursor.location = saved_cursor
    scene.geprep.origin_depth = saved_depth
    for item in made_objects:
        bpy.data.objects.remove(item, do_unlink=True)
    for mesh in made_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for action in [a for a in bpy.data.actions if a.name.startswith(prefix)]:
        bpy.data.actions.remove(action)
    print("Temporary test data removed")
""")

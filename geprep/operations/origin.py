"""Move object origins without moving the mesh geometry.

The origin is placed on the bounds of the mesh in local space: a 3 x 3 grid
across local X (left to right) and local Z (bottom to top), plus a depth
along local Y. In Blender's front view the front face is at the lowest Y.
"""

from array import array

from mathutils import Matrix, Vector

from ..helpers.objects import has_animation

ORIGIN_POSITIONS = (
    ("TL", "Top Left", "Move the origin to the top left of the mesh bounds"),
    ("TC", "Top Center", "Move the origin to the top center of the mesh bounds"),
    ("TR", "Top Right", "Move the origin to the top right of the mesh bounds"),
    (
        "CL",
        "Center Left",
        "Move the origin to the middle of the left side of the mesh bounds",
    ),
    ("C", "Center", "Move the origin to the center of the mesh bounds"),
    (
        "CR",
        "Center Right",
        "Move the origin to the middle of the right side of the mesh bounds",
    ),
    ("BL", "Bottom Left", "Move the origin to the bottom left of the mesh bounds"),
    (
        "BC",
        "Bottom Center",
        "Move the origin to the bottom center of the mesh bounds",
    ),
    (
        "BR",
        "Bottom Right",
        "Move the origin to the bottom right of the mesh bounds",
    ),
    ("CURSOR", "3D Cursor", "Place every selected mesh origin at the 3D Cursor"),
)

ORIGIN_DEPTHS = (
    ("FRONT", "Front", "Place the origin on the front of the mesh bounds (lowest Y)"),
    ("CENTER", "Center", "Place the origin halfway through the mesh bounds"),
    ("BACK", "Back", "Place the origin on the back of the mesh bounds (highest Y)"),
)

# (X factor, Z factor) inside the bounds. 0 is the minimum, 1 the maximum.
ORIGIN_FACTORS = {
    "TL": (0.0, 1.0), "TC": (0.5, 1.0), "TR": (1.0, 1.0),
    "CL": (0.0, 0.5), "C": (0.5, 0.5), "CR": (1.0, 0.5),
    "BL": (0.0, 0.0), "BC": (0.5, 0.0), "BR": (1.0, 0.0),
}

DEPTH_FACTORS = {"FRONT": 0.0, "CENTER": 0.5, "BACK": 1.0}

MAX_PROBLEMS_SHOWN = 4


def bounds_point(minimum, maximum, position, depth="CENTER"):
    """Pick a point in the bounds. Returns an (x, y, z) tuple."""
    x_factor, z_factor = ORIGIN_FACTORS[position]
    factors = (x_factor, DEPTH_FACTORS[depth], z_factor)

    return tuple(
        low + (high - low) * factor
        for low, high, factor in zip(minimum, maximum, factors)
    )


def local_bounds_point(mesh, position, depth="CENTER"):
    """Find the chosen point in the mesh's local bounds."""
    if not mesh.vertices:
        raise ValueError(
            "This mesh has no vertices. There is nowhere to place its origin"
        )

    coordinates = array("f", [0.0]) * (len(mesh.vertices) * 3)
    mesh.vertices.foreach_get("co", coordinates)
    minimum = [min(coordinates[axis::3]) for axis in range(3)]
    maximum = [max(coordinates[axis::3]) for axis in range(3)]

    return Vector(bounds_point(minimum, maximum, position, depth))


def cursor_point(obj, cursor):
    """The 3D cursor in the object's local space."""
    try:
        return obj.matrix_world.inverted() @ cursor
    except ValueError:
        raise ValueError(
            f"'{obj.name}' has a non-invertible transform. "
            "Check for zero scale"
        ) from None


def origin_problems(obj):
    """List the reasons this object's origin cannot be moved safely."""
    name = f"'{obj.name}'"
    mesh = obj.data
    problems = []

    if obj.geprep_checker.active:
        problems.append(f"{name} has a checker preview. Remove it first")

    if obj.library is not None or not obj.is_editable:
        problems.append(f"{name} cannot be edited. Make it local first")
    elif obj.override_library is not None:
        problems.append(f"{name} is a library override. Use a local copy")

    if not mesh.is_editable:
        problems.append(f"{name}: the mesh cannot be edited. Make it local first")

    users = mesh.users - int(mesh.use_fake_user)

    if users > 1:
        problems.append(
            f"{name}: the mesh is shared by {users} users. "
            "Make it single user first"
        )

    # A modifier that is only on for render still changes the render when
    # the origin moves, so either switch counts.
    enabled = [
        modifier.name
        for modifier in obj.modifiers
        if modifier.show_viewport or modifier.show_render
    ]

    if enabled:
        problems.append(
            f"{name}: apply or turn off these modifiers (viewport and "
            "render) first: " + ", ".join(enabled)
        )

    if obj.constraints:
        problems.append(
            f"{name} has constraints: "
            + ", ".join(constraint.name for constraint in obj.constraints)
        )

    if (
        has_animation(obj)
        or has_animation(mesh)
        or has_animation(mesh.shape_keys)
    ):
        problems.append(f"{name} has animation or drivers")

    if obj.parent is not None and obj.parent_type != "OBJECT":
        kind = obj.parent_type.lower().replace("_", " ")
        problems.append(f"{name} uses {kind} parenting. Use object parenting")

    for child in obj.children:
        if child.library is not None or not child.is_editable:
            problems.append(
                f"Child '{child.name}' cannot be edited. Make it local first"
            )
        elif child.override_library is not None:
            problems.append(
                f"Child '{child.name}' is a library override. "
                "Use a local copy"
            )

        if child.parent_type != "OBJECT":
            kind = child.parent_type.lower().replace("_", " ")
            problems.append(
                f"Child '{child.name}' uses {kind} parenting. "
                "Use object parenting"
            )

    return problems


def all_origin_problems(objects):
    """Collect the problems of every object, so they can be fixed at once."""
    return [
        problem
        for obj in objects
        for problem in origin_problems(obj)
    ]


def summarize_problems(problems):
    """Join problems into one message, showing only the first few."""
    shown = problems[:MAX_PROBLEMS_SHOWN]

    if len(problems) > MAX_PROBLEMS_SHOWN:
        shown.append(f"and {len(problems) - MAX_PROBLEMS_SHOWN} more")

    return "; ".join(shown)


def origin_targets(objects, position, depth, cursor):
    """Pair every object with its new origin in local space."""
    if position == "CURSOR":
        return [(obj, cursor_point(obj, cursor)) for obj in objects]

    return [
        (obj, local_bounds_point(obj.data, position, depth))
        for obj in objects
    ]


def move_mesh_origins(context, targets):
    """Move origins without moving the meshes or their children.

    `targets` is a list of (object, point in local space). The meshes are
    shifted the opposite way and the objects move by the same amount, so
    nothing changes in the scene. Children get a matching parent inverse.
    Everything is restored when something fails.
    """
    records = []
    child_inverses = {}

    for obj, point in targets:
        for child in obj.children:
            child_inverses[child] = child.matrix_parent_inverse.copy()

        records.append({
            "obj": obj,
            "point": point.copy(),
            "location": obj.location.copy(),
            "local_shift": obj.matrix_basis.to_3x3() @ point,
            "shifted": False,
        })

    try:
        for record in records:
            obj = record["obj"]
            point = record["point"]
            mesh = obj.data
            mesh.transform(Matrix.Translation(-point), shape_keys=True)
            record["shifted"] = True
            mesh.update()
            obj.location = record["location"] + record["local_shift"]

            for child in obj.children:
                child.matrix_parent_inverse = (
                    Matrix.Translation(-point) @ child_inverses[child]
                )

        context.view_layer.update()

    except Exception:
        for record in reversed(records):
            obj = record["obj"]
            obj.location = record["location"]

            if record["shifted"]:
                obj.data.transform(
                    Matrix.Translation(record["point"]),
                    shape_keys=True,
                )
                obj.data.update()

        for child, inverse in child_inverses.items():
            child.matrix_parent_inverse = inverse

        context.view_layer.update()
        raise

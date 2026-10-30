exec("""
import math
import uuid

import bpy
from mathutils import Matrix
from geprep.operations.uv import inspect_uv_mesh


prefix = f"GEPrep_UVFindingTest_{uuid.uuid4().hex[:8]}"
meshes = []
identity = Matrix.Identity(4)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def make_plane(label, scale=1.0, offset=0.0, mirrored=False):
    mesh = bpy.data.meshes.new(f"{prefix}_{label}")
    meshes.append(mesh)
    mesh.from_pydata(
        [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()

    layer = mesh.uv_layers.new(name="UVMap")

    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        u = 1.0 - co.x if mirrored else co.x
        layer.data[loop.index].uv = (
            u * scale + offset,
            co.y * scale,
        )

    return mesh


def make_two_quads(label, scale, second_offset):
    mesh = bpy.data.meshes.new(f"{prefix}_{label}")
    meshes.append(mesh)
    mesh.from_pydata(
        [
            (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (2, 0, 0), (3, 0, 0), (3, 1, 0), (2, 1, 0),
        ],
        [],
        [(0, 1, 2, 3), (4, 5, 6, 7)],
    )
    mesh.update()

    layer = mesh.uv_layers.new(name="UVMap")

    for polygon in mesh.polygons:
        shift = second_offset if polygon.index == 1 else 0.0

        for loop_index in polygon.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            layer.data[loop_index].uv = (
                (co.x - 2.0 * polygon.index) * scale + shift,
                co.y * scale,
            )

    return mesh


def make_concave_with_island(label, first_loop):
    mesh = bpy.data.meshes.new(f"{prefix}_{label}")
    meshes.append(mesh)
    outline = [(0, 0), (1, 0), (1, .5), (.5, .5), (.5, 1), (0, 1)]
    outline = outline[first_loop:] + outline[:first_loop]
    verts = [(x, y, 0) for x, y in outline]
    verts += [(2, 0, 0), (3, 0, 0), (3, 1, 0), (2, 1, 0)]
    mesh.from_pydata(verts, [], [(0, 1, 2, 3, 4, 5), (6, 7, 8, 9)])
    mesh.update()

    layer = mesh.uv_layers.new(name="UVMap")
    notch = [(0.62, 0.62), (0.9, 0.62), (0.9, 0.9), (0.62, 0.9)]

    for polygon in mesh.polygons:
        for position, loop_index in enumerate(polygon.loop_indices):
            if polygon.index == 0:
                x, y = outline[position]
            else:
                x, y = notch[position]
            layer.data[loop_index].uv = (x, y)

    return mesh


def inspect(mesh, target=1024.0, tolerance=10.0, matrix=None):
    return inspect_uv_mesh(
        mesh,
        identity if matrix is None else matrix,
        1.0,
        width=1024,
        height=1024,
        target=target,
        tolerance=tolerance,
    )


try:
    plane = make_plane("Correct")
    original_uvs = [
        tuple(item.uv)
        for item in plane.uv_layers.active.data
    ]

    result = inspect(plane)
    check(
        not any(result["findings"].values())
        and not result["mismatched_islands"],
        "Correct density and UV layout have no findings",
    )

    result = inspect(plane, target=512)
    check(
        result["mismatched_islands"] == [0]
        and result["findings"]["density"] == [0],
        "Island outside density target reports its faces",
    )

    within = make_plane("WithinTolerance", scale=0.95)
    outside = make_plane("OutsideTolerance", scale=0.8)

    check(
        not inspect(within)["mismatched_islands"]
        and inspect(outside)["mismatched_islands"] == [0],
        "Percentage tolerance distinguishes acceptable density",
    )

    lower_boundary = make_plane("LowerBoundary", scale=0.5)
    upper_boundary = make_plane("UpperBoundary", scale=1.5)

    check(
        not inspect(lower_boundary, tolerance=50)["mismatched_islands"]
        and not inspect(upper_boundary, tolerance=50)["mismatched_islands"],
        "Exact tolerance boundaries are accepted",
    )

    outside_tile = make_plane("OutsideTile", offset=0.25)
    result = inspect(outside_tile)

    check(
        result["findings"]["outside_tile"] == [0]
        and not result["findings"]["density"],
        "Outside-tile finding is independent of density",
    )
    check(
        not inspect(plane)["findings"]["outside_tile"],
        "UVs exactly on tile boundaries are accepted",
    )

    mirrored = make_plane("Mirrored", mirrored=True)
    result = inspect(mirrored)

    check(
        result["findings"]["mirrored"] == [0]
        and not result["findings"]["density"],
        "Mirroring reported without a false density mismatch",
    )

    collapsed = make_plane("Collapsed", scale=0)
    result = inspect(collapsed)

    check(
        result["findings"]["collapsed_uv"] == [0]
        and result["findings"]["density"] == [0]
        and not result["findings"]["unmeasurable"],
        "Collapsed UVs have measurable zero density",
    )

    zero_scale = Matrix.Diagonal((0.0, 1.0, 1.0, 1.0))
    result = inspect(plane, matrix=zero_scale)

    check(
        result["density"] is None
        and result["minimum_density"] is None
        and result["maximum_density"] is None
        and result["unmeasurable_islands"] == [0]
        and result["findings"]["unmeasurable"] == [0]
        and result["findings"]["degenerate_mesh"] == [0]
        and not result["findings"]["density"],
        "Zero-area geometry distinguished from a density mismatch",
    )

    for target, tolerance in [
        (0, 10), (-1, 10), (math.nan, 10), (math.inf, 10),
        (1024, -1), (1024, 101), (1024, math.nan),
    ]:
        try:
            inspect(plane, target=target, tolerance=tolerance)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid target or tolerance accepted")

    check(True, "Invalid density targets and tolerances rejected")
    check(
        [
            tuple(item.uv)
            for item in plane.uv_layers.active.data
        ] == original_uvs,
        "Inspection leaves source UVs unchanged",
    )

    result = inspect(plane)
    check(
        result["findings"]["overlap"] == []
        and abs(result["coverage"] - 1.0) < 0.01,
        "A single full-tile face has 100% coverage and no overlap",
    )

    overlapping = make_two_quads("Overlap", scale=0.5, second_offset=0.25)
    result = inspect(overlapping)
    check(
        result["findings"]["overlap"] == [0, 1],
        "Two partly overlapping faces are both reported",
    )
    check(
        abs(result["coverage"] - (0.25 + 0.25 - 0.125)) < 0.01,
        "Overlapping area is counted once in the coverage",
    )

    separate = make_two_quads("Separate", scale=0.4, second_offset=0.5)
    result = inspect(separate)
    check(
        result["findings"]["overlap"] == []
        and abs(result["coverage"] - 0.32) < 0.01,
        "Separate faces have no overlap and the expected coverage",
    )

    for first_loop in range(6):
        concave = make_concave_with_island(f"Concave{first_loop}", first_loop)
        result = inspect(concave)
        check(
            result["findings"]["overlap"] == []
            and abs(result["coverage"] - (0.75 + 0.28 ** 2)) < 0.01,
            f"Concave n-gon is not filled in (first loop {first_loop})",
        )

    print("ALL UV FINDING TESTS PASSED")

finally:
    for mesh in meshes:
        bpy.data.meshes.remove(mesh)

    print("Temporary test meshes removed")
""")

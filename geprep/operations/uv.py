import bpy

import math

import numpy as np

from functools import partial
from .mesh import apply_mesh_fix
from .uv_overlap import measure_tile_coverage


UV_FINDINGS = (
    ("density", "Outside Density Target"),
    ("outside_tile", "Outside 0–1 Tile"),
    ("overlap", "Overlapping UV Faces"),
    ("collapsed_uv", "Collapsed UV Faces"),
    ("degenerate_mesh", "Degenerate Mesh Faces"),
    ("mirrored", "Mirrored UV Faces"),
    ("unmeasurable", "Faces Without Measurable Density"),
)


def read_uv_map(mesh, name=""):
    """Read the named UV map, or the active map when no name is supplied."""
    if mesh.is_editmode:
        raise ValueError("Return to Object Mode before checking UVs")

    if name:
        layer = mesh.uv_layers.get(name)

        if layer is None:
            raise ValueError(f"UV map {name!r} is missing")

    else:
        layer = mesh.uv_layers.active

        if layer is None:
            raise ValueError("This mesh has no active UV map")

    coordinates = [
        tuple(loop.uv)
        for loop in layer.data
    ]

    if any(
        not all(math.isfinite(value) for value in coordinate)
        for coordinate in coordinates
    ):
        raise ValueError("The UV map contains invalid coordinates")

    return layer.name, coordinates


def signed_uv_triangle_area(a, b, c):
    """Return signed UV area; negative values indicate mirrored winding."""
    return (
        (b[0] - a[0]) * (c[1] - a[1])
        - (b[1] - a[1]) * (c[0] - a[0])
    ) * 0.5


def find_uv_islands(mesh, coordinates, *, epsilon=0.000001):
    """Group faces connected across edges with matching UV endpoints."""
    if len(coordinates) != len(mesh.loops):
        raise ValueError("UV coordinates do not match the mesh corners")

    if not math.isfinite(epsilon) or epsilon < 0:
        raise ValueError("UV matching tolerance must be finite and nonnegative")

    parents = list(range(len(mesh.polygons)))

    def root(index):
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]

        return index

    def join(a, b):
        a = root(a)
        b = root(b)

        if a != b:
            parents[b] = a

    def matches(a, b):
        return (
            abs(a[0] - b[0]) <= epsilon
            and abs(a[1] - b[1]) <= epsilon
        )

    sides = [[] for _ in mesh.edges]

    for polygon in mesh.polygons:
        loops = list(polygon.loop_indices)

        for current, following in zip(
            loops,
            loops[1:] + loops[:1],
        ):
            current_loop = mesh.loops[current]
            following_loop = mesh.loops[following]

            a = coordinates[current]
            b = coordinates[following]

            # Compare both sides using the same mesh-vertex order.
            if current_loop.vertex_index > following_loop.vertex_index:
                a, b = b, a

            sides[current_loop.edge_index].append(
                (polygon.index, a, b)
            )

    for adjacent in sides:
        for index, (face_a, start_a, end_a) in enumerate(adjacent):
            for face_b, start_b, end_b in adjacent[index + 1:]:
                if (
                    matches(start_a, start_b)
                    and matches(end_a, end_b)
                ):
                    join(face_a, face_b)

    islands = {}

    for polygon in mesh.polygons:
        islands.setdefault(root(polygon.index), []).append(
            polygon.index
        )

    return list(islands.values())


def measure_uv_density(
    mesh,
    matrix_world,
    unit_scale,
    *,
    uv_name="",
    width=2048,
    height=2048,
):
    """Measure area-based texel density in pixels per metre."""
    if not math.isfinite(unit_scale) or unit_scale <= 0:
        raise ValueError(
            "Scene Unit Scale must be finite and greater than zero"
        )

    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("Texture dimensions must be positive integers")

    name, coordinates = read_uv_map(mesh, uv_name)

    if not mesh.polygons:
        raise ValueError("This mesh has no faces to measure")

    face_groups = find_uv_islands(mesh, coordinates)
    islands = []
    face_islands = {}

    for index, faces in enumerate(face_groups):
        islands.append({
            "faces": faces,
            "surface_area": 0.0,
            "pixel_area": 0.0,
            "density": None,
        })

        for face in faces:
            face_islands[face] = index

    # Omit translation; it does not affect surface area.
    transform = matrix_world.to_3x3() * unit_scale
    points = [
        transform @ vertex.co
        for vertex in mesh.vertices
    ]

    if any(
        not all(math.isfinite(component) for component in point)
        for point in points
    ):
        raise ValueError("The mesh contains invalid transformed coordinates")

    collapsed_uv_faces = set()
    degenerate_mesh_faces = set()
    mirrored_faces = set()

    mesh.calc_loop_triangles()

    for triangle in mesh.loop_triangles:
        face_index = triangle.polygon_index
        island = islands[face_islands[face_index]]

        a, b, c = [
            points[index]
            for index in triangle.vertices
        ]
        surface_area = (b - a).cross(c - a).length * 0.5

        uv_a, uv_b, uv_c = [
            coordinates[index]
            for index in triangle.loops
        ]
        signed_area = signed_uv_triangle_area(uv_a, uv_b, uv_c)
        uv_area = abs(signed_area)
        pixel_area = uv_area * width * height

        if not all(
            math.isfinite(value)
            for value in (surface_area, signed_area, pixel_area)
        ):
            raise ValueError("The mesh or UV map contains invalid areas")

        if uv_area <= 1e-20:
            collapsed_uv_faces.add(face_index)

        if signed_area < -1e-20:
            mirrored_faces.add(face_index)

        if surface_area <= 1e-20:
            degenerate_mesh_faces.add(face_index)
            continue

        island["surface_area"] += surface_area
        island["pixel_area"] += pixel_area

    for island in islands:
        surface_area = island["surface_area"]
        pixel_area = island["pixel_area"]

        if not (
            math.isfinite(surface_area)
            and math.isfinite(pixel_area)
        ):
            raise ValueError("UV island area exceeds the supported range")

        if surface_area > 1e-20:
            island["density"] = math.sqrt(
                pixel_area / surface_area
            )

    total_surface_area = sum(
        island["surface_area"]
        for island in islands
    )
    total_pixel_area = sum(
        island["pixel_area"]
        for island in islands
    )

    if not (
        math.isfinite(total_surface_area)
        and math.isfinite(total_pixel_area)
    ):
        raise ValueError("Total UV measurement exceeds the supported range")

    density = (
        math.sqrt(total_pixel_area / total_surface_area)
        if total_surface_area > 1e-20
        else None
    )

    return {
        "uv_name": name,
        "density": density,
        "surface_area": total_surface_area,
        "pixel_area": total_pixel_area,
        "islands": islands,
        "collapsed_uv_faces": sorted(collapsed_uv_faces),
        "degenerate_mesh_faces": sorted(degenerate_mesh_faces),
        "mirrored_faces": sorted(mirrored_faces),
    }


def inspect_uv_mesh(
    mesh,
    matrix_world,
    unit_scale,
    *,
    uv_name="",
    width=2048,
    height=2048,
    target=512.0,
    tolerance=10.0,
):
    """Measure UV density and collect faces requiring inspection."""
    if not math.isfinite(target) or target <= 0:
        raise ValueError(
            "Target Density must be finite and greater than zero"
        )

    if (
        not math.isfinite(tolerance)
        or tolerance < 0
        or tolerance > 100
    ):
        raise ValueError(
            "Density Tolerance must be between 0 and 100 percent"
        )

    result = measure_uv_density(
        mesh,
        matrix_world,
        unit_scale,
        uv_name=uv_name,
        width=width,
        height=height,
    )

    _, coordinates = read_uv_map(mesh, result["uv_name"])
    allowed_difference = target * tolerance / 100.0

    mismatched = []
    unmeasurable = []
    density_faces = []
    unmeasurable_faces = []

    for index, island in enumerate(result["islands"]):
        density = island["density"]

        if density is None:
            unmeasurable.append(index)
            unmeasurable_faces.extend(island["faces"])

        elif abs(density - target) > allowed_difference:
            mismatched.append(index)
            density_faces.extend(island["faces"])

    outside_tile_faces = []
    tile_epsilon = 0.000001

    for polygon in mesh.polygons:
        indices = polygon.loop_indices

        if any(
            u < -tile_epsilon
            or v < -tile_epsilon
            or u > 1.0 + tile_epsilon
            or v > 1.0 + tile_epsilon
            for u, v in (
                coordinates[index]
                for index in indices
            )
        ):
            outside_tile_faces.append(polygon.index)

    # Use Blender's own tessellation (what rendering and baking sample),
    # so concave faces are not filled in by a simple fan.
    mesh.calc_loop_triangles()
    triangle_count = len(mesh.loop_triangles)
    triangles = np.empty(triangle_count * 3, dtype=np.int64)
    triangle_polygons = np.empty(triangle_count, dtype=np.int64)
    mesh.loop_triangles.foreach_get("loops", triangles)
    mesh.loop_triangles.foreach_get("polygon_index", triangle_polygons)
    triangles = triangles.reshape(-1, 3)
    coverage, overlapping_faces = measure_tile_coverage(
        np.array(coordinates, dtype=float).reshape(-1, 2),
        triangles,
        triangle_polygons,
    )

    densities = [
        island["density"]
        for island in result["islands"]
        if island["density"] is not None
    ]

    result.update({
        "minimum_density": min(densities) if densities else None,
        "maximum_density": max(densities) if densities else None,
        "mismatched_islands": mismatched,
        "unmeasurable_islands": unmeasurable,
        "coverage": coverage,
        "findings": {
            "density": sorted(density_faces),
            "outside_tile": outside_tile_faces,
            "overlap": overlapping_faces,
            "collapsed_uv": result["collapsed_uv_faces"],
            "degenerate_mesh": result["degenerate_mesh_faces"],
            "mirrored": result["mirrored_faces"],
            "unmeasurable": sorted(unmeasurable_faces),
        },
    })

    return result


def plan_uv_density(
    mesh,
    matrix_world,
    unit_scale,
    *,
    uv_name="",
    width=2048,
    height=2048,
    target=512.0,
):
    """Plan island resizing without changing the mesh or UV map."""
    if not math.isfinite(target) or target <= 0:
        raise ValueError(
            "Target Density must be finite and greater than zero"
        )

    result = measure_uv_density(
        mesh,
        matrix_world,
        unit_scale,
        uv_name=uv_name,
        width=width,
        height=height,
    )

    name, coordinates = read_uv_map(mesh, result["uv_name"])
    layer = mesh.uv_layers.get(name)

    if any(loop.pin_uv for loop in layer.data):
        raise ValueError(
            "The UV map has pinned points. "
            "Unpin them before setting density"
        )

    reasons = []

    if result["degenerate_mesh_faces"]:
        reasons.append(
            "The mesh contains degenerate triangles. "
            "Run Mesh Checks and fix the geometry"
        )

    if result["collapsed_uv_faces"]:
        reasons.append(
            "The UV map contains collapsed triangles. "
            "Fix the UV unwrap"
        )

    if reasons:
        raise ValueError("; ".join(reasons))

    output = list(coordinates)
    changed_islands = 0

    for island in result["islands"]:
        density = island["density"]

        if density is None or density <= 0:
            raise ValueError(
                "A UV island has no usable density measurement"
            )

        if math.isclose(density, target, rel_tol=0.000001):
            continue

        factor = target / density

        if not math.isfinite(factor) or factor <= 0:
            raise ValueError("The required UV scale is invalid")

        indices = [
            loop_index
            for face_index in island["faces"]
            for loop_index in mesh.polygons[face_index].loop_indices
        ]

        center = tuple(
            (
                min(coordinates[index][axis] for index in indices)
                + max(coordinates[index][axis] for index in indices)
            ) * 0.5
            for axis in (0, 1)
        )

        for index in indices:
            output[index] = tuple(
                center[axis]
                + (coordinates[index][axis] - center[axis]) * factor
                for axis in (0, 1)
            )

        changed_islands += 1

    for index, coordinate in enumerate(output):
        if not all(math.isfinite(value) for value in coordinate):
            raise ValueError(
                f"UV corner {index}: invalid coordinates after resizing"
            )

        if any(abs(value) >= 1e30 for value in coordinate):
            raise ValueError(
                f"UV corner {index}: coordinates are too large after resizing"
            )

    return {
        "uv_name": name,
        "coordinates": output,
        "changed_islands": changed_islands,
    }


def build_uv_density_mesh(
    mesh,
    *,
    matrix_world,
    unit_scale,
    uv_name="",
    width=2048,
    height=2048,
    target=512.0,
):
    """Write a density plan to an independent mesh copy."""
    proposal = plan_uv_density(
        mesh,
        matrix_world,
        unit_scale,
        uv_name=uv_name,
        width=width,
        height=height,
        target=target,
    )

    count = proposal["changed_islands"]

    if not count:
        return None, "All UV islands already match the target density"

    working = None

    try:
        working = mesh.copy()
        working.use_fake_user = False
        layer = working.uv_layers.get(proposal["uv_name"])

        if layer is None:
            raise RuntimeError("The copied mesh is missing the UV map")

        coordinates = proposal["coordinates"]

        if len(layer.data) != len(coordinates):
            raise RuntimeError("The copied UV map has a different corner count")

        for loop, coordinate in zip(layer.data, coordinates):
            loop.uv = coordinate

        working.update()

        noun = "island" if count == 1 else "islands"
        message = f"Resized {count} UV {noun} to {target:g} px/m"

        result = working
        working = None
        return result, message

    finally:
        if working is not None and working.users == 0:
            bpy.data.meshes.remove(working)


def apply_uv_density(
    context,
    obj,
    *,
    uv_name="",
    width=2048,
    height=2048,
    target=512.0,
):
    """Set base-mesh UV density through the shared assignment helper."""
    context.view_layer.update()

    build_fix = partial(
        build_uv_density_mesh,
        matrix_world=obj.matrix_world.copy(),
        unit_scale=context.scene.unit_settings.scale_length,
        uv_name=uv_name,
        width=width,
        height=height,
        target=target,
    )

    return apply_mesh_fix(
        context,
        obj,
        build_fix,
        require_applied_modifiers=False,
    )

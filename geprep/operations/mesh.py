import bpy
import math

import bmesh
from mathutils.kdtree import KDTree

from ..helpers.objects import has_animation, restore_material_links


MESH_FINDINGS = (
    ("ngons", "N-gons", "FACE"),
    ("loose_vertices", "Loose vertices", "VERT"),
    ("loose_edges", "Loose edges", "EDGE"),
    ("nearby_vertices", "Nearby vertices", "VERT"),
    ("short_edges", "Near-zero edges", "EDGE"),
    ("small_faces", "Small-area faces", "FACE"),
    ("boundaries", "Open boundary edges", "EDGE"),
    ("nonmanifold_edges", "Edges with more than two faces", "EDGE"),
    ("nonmanifold_vertices", "Non-manifold vertices", "VERT"),
    ("winding", "Winding conflicts", "EDGE"),
)


def find_nearby_vertices(points, distance):
    """Find vertices with another vertex within the distance."""
    if len(points) < 2:
        return []

    tree = KDTree(len(points))

    for index, point in enumerate(points):
        tree.insert(point, index)

    tree.balance()

    found = []

    for index, point in enumerate(points):
        nearest = tree.find_n(point, 2)

        if any(
            other_index != index and separation <= distance
            for _, other_index, separation in nearest
        ):
            found.append(index)

    return found


def find_nonmanifold_vertices(mesh):
    """Find vertices Blender classifies as non-manifold."""
    bm = bmesh.new()

    try:
        bm.from_mesh(mesh)
        bm.verts.index_update()

        return [
            vertex.index
            for vertex in bm.verts
            if not vertex.is_manifold
        ]

    finally:
        bm.free()


def inspect_base_mesh(mesh, matrix_world, unit_scale, distance):
    """Inspect base geometry using distances in metres and areas in m²."""
    if mesh.is_editmode:
        raise ValueError("Return to Object Mode before checking this mesh")

    if not math.isfinite(distance) or distance <= 0:
        raise ValueError(
            "Small Distance must be a finite number greater than zero"
        )

    if not math.isfinite(unit_scale) or unit_scale <= 0:
        raise ValueError(
            "Scene Unit Scale must be a finite number greater than zero"
        )

    # Translation does not affect lengths or areas.
    linear = matrix_world.to_3x3()
    points = [
        (linear @ vertex.co) * unit_scale
        for vertex in mesh.vertices
    ]

    if any(
        not all(math.isfinite(component) for component in point)
        for point in points
    ):
        raise ValueError("The mesh contains invalid vertex coordinates")

    found = {
        key: []
        for key, _, _ in MESH_FINDINGS
    }

    incident = [False] * len(mesh.vertices)
    sides = [[] for _ in mesh.edges]

    for edge in mesh.edges:
        a, b = edge.vertices
        incident[a] = True
        incident[b] = True

        if (points[b] - points[a]).length <= distance:
            found["short_edges"].append(edge.index)

    for polygon in mesh.polygons:
        loops = list(polygon.loop_indices)

        if len(loops) > 4:
            found["ngons"].append(polygon.index)

        for current, following in zip(
            loops,
            loops[1:] + loops[:1],
        ):
            loop = mesh.loops[current]
            a = loop.vertex_index
            b = mesh.loops[following].vertex_index

            incident[a] = True
            sides[loop.edge_index].append(
                (polygon.index, a, b)
            )

    found["loose_vertices"] = [
        index
        for index, attached in enumerate(incident)
        if not attached
    ]

    for index, faces in enumerate(sides):
        if not faces:
            found["loose_edges"].append(index)

        elif len(faces) == 1:
            found["boundaries"].append(index)

        elif len(faces) > 2:
            found["nonmanifold_edges"].append(index)

        elif faces[0][1:] != faces[1][1:][::-1]:
            found["winding"].append(index)

    mesh.calc_loop_triangles()
    areas = [0.0] * len(mesh.polygons)

    for triangle in mesh.loop_triangles:
        a, b, c = [
            points[index]
            for index in triangle.vertices
        ]
        area = (b - a).cross(c - a).length * 0.5

        if not math.isfinite(area):
            raise ValueError("The mesh contains an invalid triangle area")

        areas[triangle.polygon_index] += area

    area_threshold = distance ** 2

    if any(not math.isfinite(area) for area in areas):
        raise ValueError("The mesh contains an invalid face area")

    found["small_faces"] = [
        index
        for index, area in enumerate(areas)
        if area <= area_threshold
    ]

    found["nearby_vertices"] = find_nearby_vertices(
        points,
        distance,
    )
    found["nonmanifold_vertices"] = find_nonmanifold_vertices(mesh)

    totals = (
        len(mesh.vertices),
        len(mesh.edges),
        len(mesh.polygons),
        len(mesh.loop_triangles),
    )

    return found, totals


def select_mesh_elements(mesh, indices, mode):
    """Select finding elements on a mesh already in Edit Mode."""
    if mode not in {"VERT", "EDGE", "FACE"}:
        raise ValueError(f"Unknown selection mode: {mode!r}")

    bm = bmesh.from_edit_mesh(mesh)
    bm.select_history.clear()

    for elements in (bm.faces, bm.edges, bm.verts):
        for element in elements:
            element.select_set(False)

    bm.select_mode = {mode}

    elements = {
        "VERT": bm.verts,
        "EDGE": bm.edges,
        "FACE": bm.faces,
    }[mode]
    elements.ensure_lookup_table()

    for index in indices:
        element = elements[index]

        for vertex in getattr(element, "verts", ()):
            vertex.hide_set(False)

        for edge in getattr(element, "edges", ()):
            edge.hide_set(False)

        element.hide_set(False)
        element.select_set(True)

    bm.select_flush_mode()
    bmesh.update_edit_mesh(
        mesh,
        loop_triangles=False,
        destructive=False,
    )


def validate_mesh_fix_data(mesh):
    """Reject mesh data that our geometry fixes do not yet support."""
    if mesh.is_editmode:
        raise ValueError("Return to Object Mode before fixing meshes")

    if mesh.shape_keys is not None:
        raise ValueError(
            "This mesh has shape keys. Use a mesh without shape keys"
        )

    if has_animation(mesh):
        raise ValueError(
            "This mesh has animation. Use an unanimated mesh copy"
        )

    if mesh.has_custom_normals:
        raise ValueError(
            "This mesh has custom normals. "
            "Decide how to preserve or remove them before using this fix"
        )


def build_remove_loose_mesh(mesh):
    """Build a cleaned mesh copy, leaving the original unchanged."""
    validate_mesh_fix_data(mesh)

    bm = bmesh.new()
    working = None

    try:
        bm.from_mesh(mesh)
        original_vertices = len(bm.verts)
        original_edges = len(bm.edges)

        loose_edges = [
            edge
            for edge in bm.edges
            if not edge.link_faces
        ]

        if loose_edges:
            bmesh.ops.delete(
                bm,
                geom=loose_edges,
                context="EDGES",
            )

        loose_vertices = [
            vertex
            for vertex in bm.verts
            if not vertex.link_edges and not vertex.link_faces
        ]

        if loose_vertices:
            bmesh.ops.delete(
                bm,
                geom=loose_vertices,
                context="VERTS",
            )

        removed_vertices = original_vertices - len(bm.verts)
        removed_edges = original_edges - len(bm.edges)

        if not removed_vertices and not removed_edges:
            return None, "No loose geometry"

        working = mesh.copy()
        working.use_fake_user = False

        bm.normal_update()
        bm.to_mesh(working)
        working.update()

        message = (
            f"Removed {removed_vertices} vertices "
            f"and {removed_edges} edges"
        )

        result = working
        working = None
        return result, message

    finally:
        bm.free()

        if working is not None and working.users == 0:
            bpy.data.meshes.remove(working)


def build_merge_by_distance_mesh(
    mesh,
    *,
    matrix_world,
    unit_scale,
    distance,
):
    """Build a merged mesh copy using a distance measured in metres."""
    validate_mesh_fix_data(mesh)

    if not math.isfinite(distance) or distance <= 0:
        raise ValueError(
            "Merge Distance must be a finite number greater than zero"
        )

    if not math.isfinite(unit_scale) or unit_scale <= 0:
        raise ValueError(
            "Scene Unit Scale must be a finite number greater than zero"
        )

    # Work in scaled coordinates without introducing world translation.
    transform = matrix_world.to_3x3() * unit_scale

    try:
        inverse = transform.inverted()

    except ValueError as error:
        raise ValueError(
            "The object has a non-invertible transform. "
            "Check for zero scale before merging"
        ) from error

    bm = bmesh.new()
    working = None

    try:
        bm.from_mesh(mesh)
        original_vertices = len(bm.verts)

        for vertex in bm.verts:
            vertex.co = transform @ vertex.co

            if not all(
                math.isfinite(component)
                for component in vertex.co
            ):
                raise ValueError(
                    "The mesh contains invalid transformed coordinates"
                )

        bmesh.ops.remove_doubles(
            bm,
            verts=list(bm.verts),
            dist=distance,
        )

        removed = original_vertices - len(bm.verts)

        if not removed:
            return None, "No vertices within merge distance"

        for vertex in bm.verts:
            vertex.co = inverse @ vertex.co

            if not all(
                math.isfinite(component)
                for component in vertex.co
            ):
                raise ValueError(
                    "Merging produced invalid vertex coordinates"
                )

        bm.normal_update()

        working = mesh.copy()
        working.use_fake_user = False
        bm.to_mesh(working)
        working.update()

        noun = "vertex" if removed == 1 else "vertices"
        message = f"Merged {removed} {noun} at {distance:g} m"

        result = working
        working = None
        return result, message

    finally:
        bm.free()

        if working is not None and working.users == 0:
            bpy.data.meshes.remove(working)


class MeshFixRecoveryError(RuntimeError):
    """A mesh fix failed and recovery was incomplete."""


def apply_mesh_fix(
    context,
    obj,
    build_fix,
    *,
    require_applied_modifiers=True,
):
    """Build and assign a mesh fix, restoring the original on failure."""
    if context.mode != "OBJECT":
        raise ValueError("Return to Object Mode before fixing meshes")

    if obj.type != "MESH":
        raise ValueError("Select a mesh object")

    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError("This object is not in the current view layer")

    if (
        not obj.is_editable
        or obj.library is not None
        or obj.override_library is not None
        or obj.is_property_readonly("data")
    ):
        raise ValueError("Use an editable local object")

    if require_applied_modifiers and obj.geprep_checker.active:
        raise ValueError("Remove the checker before applying geometry fixes")

    if require_applied_modifiers and any(
        modifier.show_viewport
        for modifier in obj.modifiers
    ):
        raise ValueError("Apply viewport-enabled modifiers first")

    original_mesh = obj.data
    original_slots = [
        (slot.link, slot.material)
        for slot in obj.material_slots
    ]
    original_material_index = obj.active_material_index

    working = None
    assignment_started = False
    stage = "build fixed mesh"

    try:
        working, message = build_fix(original_mesh)

        if working is None:
            return False, message

        if working == original_mesh:
            raise RuntimeError(
                "The mesh fix must return an independent mesh"
            )

        stage = "assign fixed mesh"
        assignment_started = True
        obj.data = working

        if obj.data != working:
            raise RuntimeError("Blender did not assign the fixed mesh")

        stage = "restore material links"
        restore_material_links(
            obj,
            original_slots,
            original_material_index,
        )

        stage = "update fixed object"
        context.view_layer.update()

        return True, message

    except Exception as error:
        error.add_note(
            f"GEPrep: failed to {stage} on object {obj.name!r}"
        )

        if assignment_started:
            try:
                obj.data = original_mesh

                restore_material_links(
                    obj,
                    original_slots,
                    original_material_index,
                )

                context.view_layer.update()

            except Exception as recovery_error:
                raise MeshFixRecoveryError(
                    f"Failed to {stage}: {error}. "
                    f"Could not restore the original mesh and "
                    f"material links: {recovery_error}. Use Undo"
                ) from recovery_error

        raise

    finally:
        if (
            working is not None
            and working != original_mesh
            and working.users == 0
        ):
            try:
                bpy.data.meshes.remove(working)

            except Exception as cleanup_error:
                raise MeshFixRecoveryError(
                    f"Could not remove the temporary fixed mesh: "
                    f"{cleanup_error}. Use Undo"
                ) from cleanup_error


def build_recalculate_normals_mesh(mesh):
    """Build a mesh copy with recalculated face winding."""
    validate_mesh_fix_data(mesh)

    bm = bmesh.new()
    working = None

    try:
        bm.from_mesh(mesh)

        if not bm.faces:
            return None, "No faces"

        bm.normal_update()

        original_normals = [
            (face, face.normal.copy())
            for face in bm.faces
        ]

        bmesh.ops.recalc_face_normals(
            bm,
            faces=list(bm.faces),
        )
        bm.normal_update()

        flipped = sum(
            face.normal.dot(original_normal) < 0
            for face, original_normal in original_normals
        )

        if not flipped:
            return None, "Face winding unchanged"

        working = mesh.copy()
        working.use_fake_user = False
        bm.to_mesh(working)
        working.update()

        noun = "face" if flipped == 1 else "faces"
        message = (
            f"Reoriented {flipped} {noun}. "
            "Inspect open surfaces manually"
        )

        result = working
        working = None
        return result, message

    finally:
        bm.free()

        if working is not None and working.users == 0:
            bpy.data.meshes.remove(working)


def build_triangulate_mesh(mesh):
    """Build a triangulated mesh copy, leaving the original unchanged."""
    validate_mesh_fix_data(mesh)

    bm = bmesh.new()
    working = None

    try:
        bm.from_mesh(mesh)

        faces = [
            face
            for face in bm.faces
            if len(face.verts) > 3
        ]

        if not faces:
            return None, "Already triangles, or no faces"

        converted = len(faces)

        bmesh.ops.triangulate(
            bm,
            faces=faces,
            quad_method="BEAUTY",
            ngon_method="BEAUTY",
        )
        bm.normal_update()

        working = mesh.copy()
        working.use_fake_user = False
        bm.to_mesh(working)
        working.update()

        noun = "face" if converted == 1 else "faces"
        message = (
            f"Triangulated {converted} {noun}. "
            f"Mesh now contains {len(bm.faces)} triangles"
        )

        result = working
        working = None
        return result, message

    finally:
        bm.free()

        if working is not None and working.users == 0:
            bpy.data.meshes.remove(working)


def build_dissolve_degenerate_mesh(
    mesh,
    *,
    matrix_world,
    unit_scale,
    distance,
):
    """Build a mesh copy with degenerate geometry dissolved."""
    validate_mesh_fix_data(mesh)

    if not math.isfinite(distance) or distance <= 0:
        raise ValueError(
            "Dissolve Distance must be a finite number greater than zero"
        )

    if not math.isfinite(unit_scale) or unit_scale <= 0:
        raise ValueError(
            "Scene Unit Scale must be a finite number greater than zero"
        )

    transform = matrix_world.to_3x3() * unit_scale

    try:
        inverse = transform.inverted()

    except ValueError as error:
        raise ValueError(
            "The object has a non-invertible transform. "
            "Check for zero scale before dissolving geometry"
        ) from error

    bm = bmesh.new()
    working = None

    try:
        bm.from_mesh(mesh)
        before = (len(bm.verts), len(bm.edges), len(bm.faces))

        for vertex in bm.verts:
            vertex.co = transform @ vertex.co

            if not all(
                math.isfinite(component)
                for component in vertex.co
            ):
                raise ValueError(
                    "The mesh contains invalid transformed coordinates"
                )

        bmesh.ops.dissolve_degenerate(
            bm,
            dist=distance,
            edges=list(bm.edges),
        )

        after = (len(bm.verts), len(bm.edges), len(bm.faces))

        if before == after:
            return None, "No degenerate geometry dissolved"

        for vertex in bm.verts:
            vertex.co = inverse @ vertex.co

            if not all(
                math.isfinite(component)
                for component in vertex.co
            ):
                raise ValueError(
                    "Dissolving produced invalid vertex coordinates"
                )

        bm.normal_update()

        working = mesh.copy()
        working.use_fake_user = False
        bm.to_mesh(working)
        working.update()

        message = (
            f"Dissolved degenerate geometry at {distance:g} m. "
            f"Vertices: {before[0]} → {after[0]}. "
            f"Edges: {before[1]} → {after[1]}. "
            f"Faces: {before[2]} → {after[2]}"
        )

        result = working
        working = None
        return result, message

    finally:
        bm.free()

        if working is not None and working.users == 0:
            bpy.data.meshes.remove(working)

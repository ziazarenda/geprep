"""Export prepared meshes as GLB files.

Objects are exported from temporary copies in a temporary scene, so the
scene unit scale can be baked in and each object can be placed at the
origin without touching the originals. The exporter names the copies
differently from the originals, so the names are written back into the
finished file.
"""

import json
import math
import os
import re
import shutil
import struct
import tempfile

import bpy
from mathutils import Matrix

class ExportBlockedError(ValueError):
    """The export was refused for a reason the user can fix.

    These are expected, so the operator reports them without a traceback.
    """


EXPORT_MODES = (
    (
        "SEPARATE",
        "Separate Files",
        "One file per object, each placed at the origin",
    ),
    (
        "ASSET_PACK",
        "Asset Pack",
        "All objects in one file, each placed at the origin",
    ),
    (
        "SCENE",
        "Scene",
        "All objects in one file, keeping their positions",
    ),
)

GLB_JSON_CHUNK = 0x4E4F534A
MAX_STEM_BYTES = 180
MAX_NOTES = 3

_RESERVED_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{index}"
    for prefix in ("COM", "LPT")
    for index in range(1, 10)
}


def glb_file_stem(name):
    """Remove characters that cannot be used in filenames."""
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", name)
    name = name.strip().rstrip(".") or "Assets"

    if name.split(".")[0].upper() in _RESERVED_NAMES:
        name = "_" + name

    while len(name.encode("utf-8")) > MAX_STEM_BYTES:
        name = name[:-1]

    return name


def default_glb_name():
    """Use the project name, or Assets if the project is unsaved."""
    return (
        os.path.splitext(os.path.basename(bpy.data.filepath))[0]
        or "Assets"
    )


def check_export_mode(mode):
    if mode not in {key for key, _, _ in EXPORT_MODES}:
        raise ValueError(f"Unknown export mode: {mode}")


def plan_glb_files(objects, folder, mode, name):
    """Choose filenames and group the objects for export.

    Returns a list of (destination, objects).
    """
    check_export_mode(mode)
    objects = sorted(objects, key=lambda obj: (obj.name.casefold(), obj.name))

    if mode != "SEPARATE":
        stem = name.strip()

        if stem.lower().endswith(".glb"):
            stem = stem[:-4]

        return [(os.path.join(folder, glb_file_stem(stem) + ".glb"), objects)]

    jobs = []
    reserved = set()

    for obj in objects:
        stem = glb_file_stem(obj.name)
        candidate = stem
        index = 1

        while candidate.casefold() in reserved:
            candidate = f"{stem}.{index:03d}"
            index += 1

        reserved.add(candidate.casefold())
        jobs.append((os.path.join(folder, candidate + ".glb"), [obj]))

    return jobs


def read_glb_document(source, size):
    """Read a GLB's JSON chunk. Returns (document, chunk_length, total)."""
    header = source.read(12)

    if len(header) != 12:
        raise ValueError("The exported GLB header is incomplete")

    magic, version, total = struct.unpack("<4sII", header)

    if magic != b"glTF":
        raise ValueError("The exported file is not a GLB")

    if version != 2:
        raise ValueError(
            f"The exporter wrote GLB version {version}. Version 2 is required"
        )

    if total != size:
        raise ValueError("The GLB file size does not match its header")

    chunk_header = source.read(8)

    if len(chunk_header) != 8:
        raise ValueError("The exported GLB is missing its scene data")

    chunk_length, chunk_type = struct.unpack("<II", chunk_header)

    if chunk_type != GLB_JSON_CHUNK:
        raise ValueError("The GLB does not start with its scene data")

    if chunk_length % 4:
        raise ValueError("The GLB scene data has invalid byte alignment")

    if chunk_length > total - 20:
        raise ValueError("The GLB scene data extends past the end of the file")

    document = json.loads(source.read(chunk_length).decode("utf-8"))

    if not document.get("meshes"):
        raise ValueError("The exported file contains no meshes")

    return document, chunk_length, total


def apply_glb_names(document, names):
    """Rename nodes and their meshes. `names` maps exported to real names."""
    meshes = document["meshes"]
    named_meshes = set()
    exported = set()

    for node in document.get("nodes", []):
        source_name = names.get(node.get("name"))

        if source_name is None:
            continue

        node["name"] = source_name
        exported.add(source_name)
        mesh_index = node.get("mesh")

        if mesh_index is not None and mesh_index not in named_meshes:
            meshes[mesh_index]["name"] = source_name
            named_meshes.add(mesh_index)

    missing = set(names.values()) - exported

    if missing:
        raise ValueError(
            "Missing exported objects: " + ", ".join(sorted(missing))
        )


def prepare_glb_names(path, names):
    """Use the original object names inside the exported file."""
    replacement = None

    try:
        with open(path, "rb") as source:
            document, chunk_length, total = read_glb_document(
                source,
                os.path.getsize(path),
            )
            apply_glb_names(document, names)
            encoded = json.dumps(
                document,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            encoded += b" " * ((-len(encoded)) % 4)

            with tempfile.NamedTemporaryFile(
                dir=os.path.dirname(path),
                suffix=".glb",
                delete=False,
            ) as output:
                replacement = output.name
                output.write(struct.pack(
                    "<4sII",
                    b"glTF",
                    2,
                    total - chunk_length + len(encoded),
                ))
                output.write(struct.pack("<II", len(encoded), GLB_JSON_CHUNK))
                output.write(encoded)
                shutil.copyfileobj(source, output)

        os.replace(replacement, path)
        replacement = None

    finally:
        if replacement is not None:
            os.unlink(replacement)


def publish_glb(temporary, destination, overwrite):
    """Save the finished export. Replace an existing file only when allowed.

    Without `overwrite` the file is created exclusively, so an existing
    file is never replaced even if it appears while exporting.
    """
    if overwrite:
        os.replace(temporary, destination)
        return

    created = False

    try:
        with open(temporary, "rb") as source:
            with open(destination, "xb") as output:
                created = True
                shutil.copyfileobj(source, output)
    except Exception:
        if created:
            os.unlink(destination)

        raise


def glb_transform_has_shear(matrix):
    """Check whether the object's transform is skewed."""
    columns = [
        tuple(matrix[row][axis] for row in range(3))
        for axis in range(3)
    ]

    for first, second in ((0, 1), (0, 2), (1, 2)):
        a, b = columns[first], columns[second]
        length_product = math.sqrt(
            sum(x * x for x in a) * sum(x * x for x in b)
        )

        if (
            length_product > 1e-20
            and abs(sum(x * y for x, y in zip(a, b)))
            > length_product * 1e-6
        ):
            return True

    return False


def export_blocker(obj):
    """Return why this object cannot be exported, or ''."""
    if obj.type != "MESH":
        return f"'{obj.name}' is not a mesh"

    if not obj.data.polygons:
        return f"'{obj.name}' has no faces to export"

    if obj.geprep_checker.active:
        return f"'{obj.name}' has a checker preview. Remove it first"

    if glb_transform_has_shear(obj.matrix_world):
        return (
            f"'{obj.name}' is skewed by its transforms. "
            "Bake the skew into its mesh before export"
        )

    enabled = [
        modifier.name
        for modifier in obj.modifiers
        if modifier.show_viewport
    ]

    if enabled:
        return (
            f"'{obj.name}': apply these modifiers before export: "
            + ", ".join(enabled)
        )

    if obj.data.shape_keys is not None:
        return (
            f"'{obj.name}' has shape keys. Use a mesh without shape keys"
        )

    return ""


def export_unit_scale(scene):
    """Return the scene unit scale, which is baked into the export."""
    scale = scene.unit_settings.scale_length

    if not math.isfinite(scale):
        raise ValueError("Scene Unit Scale is not a valid number")

    if scale <= 0:
        raise ValueError("Scene Unit Scale must be greater than zero")

    return scale


def gltf_export_arguments(filepath, *, materials, tangents):
    """Options for Blender's glTF exporter."""
    return dict(
        filepath=filepath,
        check_existing=False,
        export_format="GLB",
        use_selection=True,
        use_active_scene=True,
        use_visible=False,
        use_renderable=False,
        use_active_collection=False,
        export_texcoords=True,
        export_normals=True,
        export_tangents=tangents,
        export_materials="EXPORT" if materials else "PLACEHOLDER",
        export_cameras=False,
        export_lights=False,
        export_animations=False,
        export_skins=False,
        export_morph=False,
        export_yup=True,
        export_apply=False,
        export_extras=False,
        use_mesh_edges=False,
        use_mesh_vertices=False,
        will_save_settings=False,
    )


def exporter_problem(arguments=None):
    """Return why the glTF exporter cannot be used as configured, or ''."""
    try:
        properties = bpy.ops.export_scene.gltf.get_rna_type().properties
    except Exception:
        return (
            "Enable Blender's glTF 2.0 exporter "
            "(Preferences > Add-ons) before exporting"
        )

    if arguments is None:
        arguments = gltf_export_arguments("", materials=True, tangents=False)

    unknown = sorted(set(arguments) - set(properties.keys()))

    if unknown:
        return (
            "This Blender's glTF exporter has no option named "
            + ", ".join(unknown)
            + ". GEPrep needs an update for this Blender version"
        )

    return ""


def format_size(size):
    """Format a file size for display."""
    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size / (1024 * 1024):.1f} MB"


def material_failure_notes(object_name, inspection):
    """List failed materials from a material inspection as short notes."""
    notes = []

    for material in inspection["materials"]:
        if material["status"] != "FAILED":
            continue

        lines = [
            failure
            for texture in material["textures"]
            for failure in texture["failures"]
        ] or [material["message"].splitlines()[0]]

        notes.extend(f"{object_name}: {line}" for line in lines)

    return notes


def summarize_notes(notes):
    """Join notes into one message, showing only the first few."""
    shown = notes[:MAX_NOTES]

    if len(notes) > MAX_NOTES:
        shown.append(f"and {len(notes) - MAX_NOTES} more")

    return "\n".join(shown)


def export_glb_job(
    context,
    objects,
    destination,
    mode,
    unit_scale,
    *,
    materials,
    tangents,
    overwrite,
):
    """Export temporary copies, then return to the original scene."""
    check_export_mode(mode)

    if context.window is None:
        raise ExportBlockedError("Open a Blender window before exporting")

    for obj in objects:
        blocker = export_blocker(obj)

        if blocker:
            raise ExportBlockedError(blocker)

    original_scene = context.window.scene
    original_layer = context.window.view_layer
    matrices = [
        (obj, Matrix.Scale(unit_scale, 4) @ obj.matrix_world.copy())
        for obj in objects
    ]
    scene = None
    duplicates = []
    temporary = None

    try:
        scene = bpy.data.scenes.new("GEPrep Export Temporary")
        scene.unit_settings.system = "METRIC"
        scene.unit_settings.scale_length = 1.0
        names = {}

        for source, world in matrices:
            duplicate = source.copy()
            duplicates.append(duplicate)
            duplicate.name = "GEPrep Export " + source.name
            duplicate.parent = None
            duplicate.matrix_parent_inverse = Matrix.Identity(4)
            duplicate.animation_data_clear()
            duplicate.constraints.clear()
            duplicate.modifiers.clear()
            duplicate.instance_type = "NONE"
            duplicate.delta_location = (0, 0, 0)
            duplicate.delta_rotation_euler = (0, 0, 0)
            duplicate.delta_rotation_quaternion = (1, 0, 0, 0)
            duplicate.delta_scale = (1, 1, 1)

            if mode != "SCENE":
                world.translation = (0, 0, 0)

            duplicate.matrix_world = world
            duplicate.hide_viewport = False
            duplicate.hide_render = False
            duplicate.hide_select = False
            scene.collection.objects.link(duplicate)
            names[duplicate.name] = source.name

        context.window.scene = scene
        context.window.view_layer = scene.view_layers[0]
        layer = context.window.view_layer
        layer.update()

        for duplicate in duplicates:
            duplicate.hide_set(False, view_layer=layer)
            duplicate.select_set(True, view_layer=layer)

        layer.objects.active = duplicates[0]

        with tempfile.NamedTemporaryFile(
            dir=os.path.dirname(destination),
            prefix=".geprep-",
            suffix=".glb",
            delete=False,
        ) as file:
            temporary = file.name

        result = bpy.ops.export_scene.gltf(
            **gltf_export_arguments(
                temporary,
                materials=materials,
                tangents=tangents,
            )
        )

        if "FINISHED" not in result:
            raise RuntimeError("Blender didn't finish the GLB export")

        prepare_glb_names(temporary, names)
        size = os.path.getsize(temporary)
        publish_glb(temporary, destination, overwrite)

        return size

    finally:
        context.window.scene = original_scene
        context.window.view_layer = original_layer

        for duplicate in reversed(duplicates):
            bpy.data.objects.remove(duplicate, do_unlink=True)

        if scene is not None:
            bpy.data.scenes.remove(scene)

        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)

exec("""
import json
import os
import struct
import tempfile
import uuid

import bpy
from geprep.operations import export as ex


context = bpy.context
scene = context.scene
settings = scene.geprep
prefix = f"GEPrepExp_{uuid.uuid4().hex[:6]}"
made_objects, made_meshes, made_materials, made_images = [], [], [], []
saved = {
    key: getattr(settings, key)
    for key in ("export_folder", "export_mode", "export_name",
                "export_materials", "export_tangents", "export_overwrite")
}
saved_unit_scale = scene.unit_settings.scale_length


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def read_glb(path):
    data = open(path, "rb").read()
    magic, version, total = struct.unpack("<4sII", data[:12])
    length, kind = struct.unpack("<II", data[12:20])
    assert magic == b"glTF" and version == 2 and total == len(data)
    return json.loads(data[20:20 + length])


def make_cube(name, location=(0, 0, 0), size=1.0):
    h = size / 2
    vertices = [(-h, -h, -h), (h, -h, -h), (h, h, -h), (-h, h, -h),
                (-h, -h, h), (h, -h, h), (h, h, h), (-h, h, h)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mesh = bpy.data.meshes.new(f"{prefix}_{name}_mesh")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    mesh.uv_layers.new(name="UVMap")
    material = bpy.data.materials.new(f"{prefix}_{name}_mat")
    if not material.node_tree:
        material.use_nodes = True
    mesh.materials.append(material)
    obj = bpy.data.objects.new(f"{prefix}_{name}", mesh)
    scene.collection.objects.link(obj)
    obj.location = location
    made_objects.append(obj)
    made_meshes.append(mesh)
    made_materials.append(material)
    return obj


def select(*objects):
    for item in list(context.selected_objects):
        item.select_set(False)
    for item in objects:
        item.select_set(True)
    context.view_layer.objects.active = objects[0]


def bounds(document, node_name):
    node = next(n for n in document["nodes"] if n["name"] == node_name)
    mesh = document["meshes"][node["mesh"]]
    accessor = document["accessors"][mesh["primitives"][0]["attributes"]["POSITION"]]
    return accessor["min"], accessor["max"]


def effective_size(document, node_name):
    # glTF keeps an object's scale on its node, not in the mesh bounds.
    node = next(n for n in document["nodes"] if n["name"] == node_name)
    low, high = bounds(document, node_name)
    scale = node.get("scale", [1.0, 1.0, 1.0])
    return [(h - l) * abs(k) for l, h, k in zip(low, high, scale)]


def node_translation(document, node_name):
    node = next(n for n in document["nodes"] if n["name"] == node_name)
    return node.get("translation", [0.0, 0.0, 0.0])


def near(values, expected, tolerance=1e-4):
    return all(abs(a - b) <= tolerance for a, b in zip(values, expected))


def export_to(folder, mode, name="", **options):
    settings.export_folder = folder
    settings.export_mode = mode
    settings.export_name = name
    settings.export_materials = options.get("materials", True)
    settings.export_tangents = options.get("tangents", False)
    settings.export_overwrite = options.get("overwrite", False)
    return bpy.ops.geprep.export_glb()


try:
    a = make_cube("A", location=(5, 0, 0))
    b = make_cube("B", location=(0, 3, 0))
    base_scenes = len(bpy.data.scenes)
    base_objects = len(bpy.data.objects)
    original_scene = context.window.scene

    check(ex.exporter_problem() == "", "Every exporter option GEPrep uses exists in this Blender")

    with tempfile.TemporaryDirectory() as folder:
        # ---- separate files
        select(a, b)
        check(export_to(folder, "SEPARATE") == {"FINISHED"}, "Separate export runs")
        files = sorted(os.listdir(folder))
        check(files == [f"{a.name}.glb", f"{b.name}.glb"],
              "One file per object, named after the object")
        document = read_glb(os.path.join(folder, f"{a.name}.glb"))
        check([n["name"] for n in document["nodes"]] == [a.name],
              "The node carries the original object name")
        check(document["meshes"][0]["name"] == a.name,
              "The mesh carries the original object name")
        check(near(effective_size(document, a.name), [1.0] * 3),
              "A 1 m cube is 1 m wide in the file")
        check(near(node_translation(document, a.name), [0, 0, 0]),
              "A separate file places the object at the origin")
        results = settings.export_results
        check(len(results) == 2 and all(r.status == "EXPORTED" for r in results),
              "Both results say Exported")
        check(" B" in results[0].message or "KB" in results[0].message,
              "The result shows the file size")
        check(len(bpy.data.scenes) == base_scenes and len(bpy.data.objects) == base_objects,
              "No temporary scene or object is left behind")
        check(context.window.scene == original_scene, "The original scene is active again")

        # ---- overwrite
        modified = os.path.getmtime(os.path.join(folder, f"{a.name}.glb"))
        check(export_to(folder, "SEPARATE") == {"FINISHED"}, "A second export runs")
        check(all(r.status == "SKIPPED" for r in settings.export_results),
              "Existing files are skipped without Overwrite")
        check(os.path.getmtime(os.path.join(folder, f"{a.name}.glb")) == modified,
              "A skipped file is not touched")
        check(export_to(folder, "SEPARATE", overwrite=True) == {"FINISHED"}
              and all(r.status == "EXPORTED" for r in settings.export_results),
              "Overwrite replaces the files")
        check(not [f for f in os.listdir(folder) if f.startswith(".geprep-")],
              "No temporary export file is left in the folder")

    with tempfile.TemporaryDirectory() as folder:
        # ---- asset pack and scene
        select(a, b)
        check(export_to(folder, "ASSET_PACK", "Props.glb") == {"FINISHED"}
              and os.listdir(folder) == ["Props.glb"], "Asset pack writes one file")
        document = read_glb(os.path.join(folder, "Props.glb"))
        check(sorted(n["name"] for n in document["nodes"]) == sorted([a.name, b.name]),
              "Both objects are in the pack")
        check(near(node_translation(document, a.name), [0, 0, 0])
              and near(node_translation(document, b.name), [0, 0, 0]),
              "Pack objects are each placed at the origin")

        check(export_to(folder, "SCENE", "Level") == {"FINISHED"}, "Scene export runs")
        document = read_glb(os.path.join(folder, "Level.glb"))
        check(near(node_translation(document, a.name), [5, 0, 0]),
              "Scene mode keeps an object's position (Blender X is glTF X)")
        check(near(node_translation(document, b.name), [0, 0, -3]),
              "Y up is applied (Blender Y 3 becomes glTF Z -3)")

    # ---- unit scale
    scene.unit_settings.scale_length = 2.0
    with tempfile.TemporaryDirectory() as folder:
        select(a)
        check(export_to(folder, "SEPARATE") == {"FINISHED"}, "Export with unit scale 2 runs")
        document = read_glb(os.path.join(folder, f"{a.name}.glb"))
        check(near(effective_size(document, a.name), [2.0] * 3),
              "The scene unit scale is applied to the size")
    scene.unit_settings.scale_length = saved_unit_scale

    # ---- tangents and materials
    with tempfile.TemporaryDirectory() as folder:
        select(a)
        export_to(folder, "SEPARATE", tangents=False)
        document = read_glb(os.path.join(folder, f"{a.name}.glb"))
        check("TANGENT" not in document["meshes"][0]["primitives"][0]["attributes"],
              "Tangents are left out by default")
        check(bool(document.get("materials")), "Materials are written when included")
        export_to(folder, "SEPARATE", tangents=True, overwrite=True)
        document = read_glb(os.path.join(folder, f"{a.name}.glb"))
        check("TANGENT" in document["meshes"][0]["primitives"][0]["attributes"],
              "Tangents are written when asked for")
        export_to(folder, "SEPARATE", materials=False, overwrite=True)
        document = read_glb(os.path.join(folder, f"{a.name}.glb"))
        print("INFO: materials in a file exported without materials:",
              len(document.get("materials", [])))

    # ---- checker guard
    with tempfile.TemporaryDirectory() as folder:
        select(a, b)
        a.geprep_checker.active = True
        try:
            check(export_to(folder, "SEPARATE") == {"CANCELLED"} and os.listdir(folder) == [],
                  "An object with an active checker cancels the whole export")
        finally:
            a.geprep_checker.active = False

    # ---- a blocked object does not stop the others
    with tempfile.TemporaryDirectory() as folder:
        select(a, b)
        modifier = a.modifiers.new("Bevel", "BEVEL")
        try:
            check(export_to(folder, "SEPARATE") == {"FINISHED"}, "Export with one blocked object runs")
            by_name = {r.filename: r for r in settings.export_results}
            check(by_name[f"{a.name}.glb"].status == "FAILED"
                  and "apply these modifiers" in by_name[f"{a.name}.glb"].message,
                  "The object with an enabled modifier fails and says why")
            check(by_name[f"{b.name}.glb"].status == "EXPORTED"
                  and os.listdir(folder) == [f"{b.name}.glb"],
                  "The other object is still exported")
        finally:
            a.modifiers.remove(modifier)
        check(len(bpy.data.scenes) == base_scenes and len(bpy.data.objects) == base_objects,
              "A failed job leaves nothing behind either")

    # ---- folder problems
    try:
        export_to("", "SEPARATE")
        raise AssertionError("An empty folder should be refused")
    except RuntimeError as error:
        check("Choose an export folder" in str(error), "An empty folder is refused with a message")

    # ---- what happens with a missing texture (informational)
    with tempfile.TemporaryDirectory() as folder:
        image = bpy.data.images.new(f"{prefix}_missing", 8, 8)
        image.source = "FILE"
        image.filepath = "//definitely_not_here.png"
        made_images.append(image)
        tree = a.data.materials[0].node_tree
        texture = tree.nodes.new("ShaderNodeTexImage")
        texture.image = image
        bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
        tree.links.new(texture.outputs["Color"], bsdf.inputs["Base Color"])
        select(a)
        export_to(folder, "SEPARATE")
        entry = settings.export_results[0]
        print("INFO: missing texture export status:", entry.status)
        print("INFO: missing texture message:", entry.message.replace(chr(10), " | "))

    print("ALL EXPORT TESTS PASSED")

finally:
    scene.unit_settings.scale_length = saved_unit_scale
    for key, value in saved.items():
        setattr(settings, key, value)
    settings.export_results.clear()
    for item in made_objects:
        bpy.data.objects.remove(item, do_unlink=True)
    for mesh in made_meshes:
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for material in made_materials:
        bpy.data.materials.remove(material)
    for image in made_images:
        bpy.data.images.remove(image)
    print("Temporary test data removed")
""")

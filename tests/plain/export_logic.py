"""Plain-Python tests for operations/export.py (no Blender needed).

Run from the folder that contains the `geprep` package:
    python3 tests/export_logic.py
"""

import importlib.util
import json
import os
import struct
import sys
import tempfile
import types
from types import SimpleNamespace

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "geprep")

# ---------------------------------------------------------------- fakes
fake_bpy = types.ModuleType("bpy")
fake_bpy.data = SimpleNamespace(filepath="")
gltf_properties = {"filepath", "export_format", "export_tangents"}
fake_bpy.ops = SimpleNamespace(export_scene=SimpleNamespace(
    gltf=SimpleNamespace(
        get_rna_type=lambda: SimpleNamespace(
            properties=SimpleNamespace(keys=lambda: list(gltf_properties)),
        ),
    ),
))
sys.modules["bpy"] = fake_bpy
fake_mathutils = types.ModuleType("mathutils")
fake_mathutils.Matrix = object
sys.modules["mathutils"] = fake_mathutils

spec = importlib.util.spec_from_file_location(
    "export_ops",
    os.path.join(ROOT, "operations", "export.py"),
)
ex = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ex)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def raises(function, text, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except Exception as error:
        return text in str(error)
    return False


# ------------------------------------------------------------ file names
check(ex.glb_file_stem('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j",
      "Characters that are not allowed in file names are replaced")
check(ex.glb_file_stem("  Wall.. ") == "Wall", "Spaces and trailing dots are removed")
check(ex.glb_file_stem("") == "Assets" and ex.glb_file_stem("...") == "Assets",
      "An empty name becomes Assets")
check(ex.glb_file_stem("CON") == "_CON" and ex.glb_file_stem("com1") == "_com1"
      and ex.glb_file_stem("nul.txt") == "_nul.txt",
      "Reserved device names get a prefix")
check(ex.glb_file_stem("Console") == "Console", "Names that only start with a reserved word are untouched")
long_name = ex.glb_file_stem("é" * 200)
check(len(long_name.encode("utf-8")) <= 180 and long_name == "é" * 90,
      "Long names are cut to a safe byte length without splitting a character")
check(ex.glb_file_stem("Tür_01") == "Tür_01", "Non-ASCII names are kept")

# ------------------------------------------------------------ planning
def named(*names):
    return [SimpleNamespace(name=name) for name in names]


jobs = ex.plan_glb_files(named("b", "a", "C"), "/out", "SEPARATE", "ignored")
check([os.path.basename(path) for path, _ in jobs] == ["a.glb", "b.glb", "C.glb"]
      and all(len(members) == 1 for _, members in jobs),
      "Separate mode gives one sorted file per object")

jobs = ex.plan_glb_files(named("Wall", "wall", "Wall.001"), "/out", "SEPARATE", "")
files = [os.path.basename(path) for path, _ in jobs]
check(len({name.casefold() for name in files}) == 3 and "Wall.glb" in files,
      "File names that differ only by case never collide")

jobs = ex.plan_glb_files(named("b", "a"), "/out", "ASSET_PACK", " Props.GLB ")
check(len(jobs) == 1 and os.path.basename(jobs[0][0]) == "Props.glb"
      and [o.name for o in jobs[0][1]] == ["a", "b"],
      "A pack is one file with every object, and a .glb ending is not doubled")

jobs = ex.plan_glb_files(named("a"), "/out", "SCENE", "Level:1")
check(os.path.basename(jobs[0][0]) == "Level_1.glb", "Single-file names are cleaned too")
check(raises(ex.plan_glb_files, "Unknown export mode", named("a"), "/out", "NOPE", ""),
      "An unknown mode is refused")

# ------------------------------------------------------------ GLB rewrite
JSON, BIN = 0x4E4F534A, 0x004E4942
BINARY = bytes(range(16))


def make_glb(document, binary=BINARY):
    encoded = json.dumps(document).encode("utf-8")
    encoded += b" " * ((-len(encoded)) % 4)
    chunk = struct.pack("<II", len(binary), BIN) + binary
    total = 12 + 8 + len(encoded) + len(chunk)
    return (struct.pack("<4sII", b"glTF", 2, total)
            + struct.pack("<II", len(encoded), JSON) + encoded + chunk)


def read_glb(path):
    data = open(path, "rb").read()
    magic, version, total = struct.unpack("<4sII", data[:12])
    length, kind = struct.unpack("<II", data[12:20])
    document = json.loads(data[20:20 + length])
    rest = data[20 + length:]
    return magic, version, total, len(data), length, kind, document, rest


document = {
    "asset": {"version": "2.0"},
    "nodes": [{"name": "GEPrep Export Wall", "mesh": 0},
              {"name": "GEPrep Export Door", "mesh": 1},
              {"name": "GEPrep Export Twin", "mesh": 1},
              {"name": "Unrelated"}],
    "meshes": [{"name": "WallMesh"}, {"name": "DoorMesh"}],
}
names = {"GEPrep Export Wall": "Wall", "GEPrep Export Door": "Door",
         "GEPrep Export Twin": "Twin"}

with tempfile.TemporaryDirectory() as folder:
    path = os.path.join(folder, "a.glb")
    open(path, "wb").write(make_glb(document))
    ex.prepare_glb_names(path, names)
    magic, version, total, size, length, kind, result, rest = read_glb(path)
    check(magic == b"glTF" and version == 2 and total == size,
          "The rewritten file has a valid header and total length")
    check(kind == JSON and length % 4 == 0, "The scene data chunk stays aligned")
    check([n["name"] for n in result["nodes"]] == ["Wall", "Door", "Twin", "Unrelated"],
          "Exported node names are replaced by the original names")
    check([m["name"] for m in result["meshes"]] == ["Wall", "Door"],
          "A mesh takes the name of the first object that uses it")
    check(rest == struct.pack("<II", len(BINARY), BIN) + BINARY,
          "The binary chunk is copied unchanged")
    check(os.listdir(folder) == ["a.glb"], "No temporary file is left behind")

    # A longer name changes the chunk size and still produces a valid file.
    long_names = {"GEPrep Export Wall": "W" * 61, "GEPrep Export Door": "Door",
                  "GEPrep Export Twin": "Twin"}
    open(path, "wb").write(make_glb(document))
    ex.prepare_glb_names(path, long_names)
    magic, version, total, size, length, kind, result, rest = read_glb(path)
    check(total == size and length % 4 == 0 and result["nodes"][0]["name"] == "W" * 61
          and rest == struct.pack("<II", len(BINARY), BIN) + BINARY,
          "Longer names keep the file consistent")

    def broken(data, text, label, mapping=names):
        open(path, "wb").write(data)
        failed = raises(ex.prepare_glb_names, text, path, mapping)
        check(failed and os.listdir(folder) == ["a.glb"],
              f"{label} is refused and leaves no temporary file")
        check(open(path, "rb").read() == data, f"{label} leaves the file unchanged")

    good = make_glb(document)
    broken(good[:8], "header is incomplete", "A truncated header")
    broken(b"XXXX" + good[4:], "not a GLB", "A wrong magic number")
    broken(good[:4] + struct.pack("<I", 1) + good[8:], "version 1", "GLB version 1")
    broken(good + b"\0", "size does not match", "A wrong file size")
    broken(struct.pack("<4sII", b"glTF", 2, 12), "missing its scene data",
           "A missing chunk header")
    broken(good[:12] + struct.pack("<II", 8, BIN) + good[20:], "does not start with its scene data",
           "A first chunk that is not JSON")
    broken(good[:12] + struct.pack("<II", 6, JSON) + good[20:], "byte alignment",
           "A misaligned JSON chunk")
    broken(good[:12] + struct.pack("<II", 4000, JSON) + good[20:], "extends past",
           "A JSON chunk longer than the file")
    no_meshes = dict(document, meshes=[])
    broken(make_glb(no_meshes), "contains no meshes", "A file without meshes")
    broken(good, "Missing exported objects: Ghost", "A missing object",
           dict(names, **{"GEPrep Export Ghost": "Ghost"}))

# ------------------------------------------------------------ publishing
with tempfile.TemporaryDirectory() as folder:
    temp, target = os.path.join(folder, "t.tmp"), os.path.join(folder, "out.glb")
    open(temp, "wb").write(b"new")
    ex.publish_glb(temp, target, overwrite=False)
    check(open(target, "rb").read() == b"new" and os.path.exists(temp),
          "A new file is created from the finished export")

    open(target, "wb").write(b"old")
    check(raises(ex.publish_glb, "", temp, target, False)
          and open(target, "rb").read() == b"old",
          "An existing file is never replaced without overwrite")

    try:
        ex.publish_glb(temp, target, False)
    except FileExistsError:
        check(True, "The refusal is a FileExistsError so it is reported as Skipped")

    ex.publish_glb(temp, target, overwrite=True)
    check(open(target, "rb").read() == b"new" and not os.path.exists(temp),
          "Overwrite replaces the file")

# ------------------------------------------------------------ transforms
def matrix(*rows):
    return [list(row) + [0.0] * (4 - len(row)) for row in rows] + [[0, 0, 0, 1]]


identity = matrix((1, 0, 0), (0, 1, 0), (0, 0, 1))
rotated = matrix((0, -1, 0), (1, 0, 0), (0, 0, 1))
scaled = matrix((2, 0, 0), (0, 3, 0), (0, 0, 0.5))
sheared = matrix((1, 1, 0), (0, 1, 0), (0, 0, 1))
rotated_scaled = matrix((0, -3, 0), (2, 0, 0), (0, 0, 1))
flat = matrix((1, 0, 0), (0, 0, 0), (0, 0, 1))
check(not ex.glb_transform_has_shear(identity), "An identity transform has no shear")
check(not ex.glb_transform_has_shear(rotated), "A rotation has no shear")
check(not ex.glb_transform_has_shear(scaled), "Non-uniform scale on its own is not shear")
check(not ex.glb_transform_has_shear(rotated_scaled), "Rotation plus scale is not shear")
check(ex.glb_transform_has_shear(sheared), "A skewed transform is detected")
check(not ex.glb_transform_has_shear(flat), "A zero-length axis does not count as shear")

# ------------------------------------------------------------ blockers
def fake_object(**changes):
    values = dict(
        name="Wall",
        type="MESH",
        data=SimpleNamespace(polygons=[1], shape_keys=None),
        geprep_checker=SimpleNamespace(active=False),
        matrix_world=identity,
        modifiers=[],
    )
    values.update(changes)
    return SimpleNamespace(**values)


check(ex.export_blocker(fake_object()) == "", "A clean mesh can be exported")
check("not a mesh" in ex.export_blocker(fake_object(type="CURVE")), "A non-mesh is refused")
check("no faces" in ex.export_blocker(fake_object(
    data=SimpleNamespace(polygons=[], shape_keys=None))), "A mesh without faces is refused")
check("checker preview" in ex.export_blocker(fake_object(
    geprep_checker=SimpleNamespace(active=True))), "An active checker is refused")
check("skewed" in ex.export_blocker(fake_object(matrix_world=sheared)), "A skewed object is refused")
check("Mirror, Array" in ex.export_blocker(fake_object(modifiers=[
    SimpleNamespace(name="Mirror", show_viewport=True),
    SimpleNamespace(name="Off", show_viewport=False),
    SimpleNamespace(name="Array", show_viewport=True)])),
    "Enabled modifiers are named, disabled ones are not")
check("Off" not in ex.export_blocker(fake_object(modifiers=[
    SimpleNamespace(name="Off", show_viewport=False),
    SimpleNamespace(name="Array", show_viewport=True)])),
    "A disabled modifier is not mentioned")
check("shape keys" in ex.export_blocker(fake_object(
    data=SimpleNamespace(polygons=[1], shape_keys=object()))), "Shape keys are refused")

# ------------------------------------------------------------ unit scale
for value, text in ((float("nan"), "not a valid number"), (float("inf"), "not a valid number"),
                    (0, "greater than zero"), (-1, "greater than zero")):
    scene = SimpleNamespace(unit_settings=SimpleNamespace(scale_length=value))
    check(raises(ex.export_unit_scale, text, scene), f"Unit scale {value} is refused")
check(ex.export_unit_scale(SimpleNamespace(
    unit_settings=SimpleNamespace(scale_length=0.01))) == 0.01, "A valid unit scale is returned")

# ------------------------------------------------------------ exporter options
arguments = ex.gltf_export_arguments("/tmp/x.glb", materials=True, tangents=False)
check(arguments["export_materials"] == "EXPORT" and arguments["export_tangents"] is False
      and arguments["export_format"] == "GLB" and arguments["export_yup"] is True
      and arguments["will_save_settings"] is False and arguments["check_existing"] is False,
      "Export options follow the settings")
arguments = ex.gltf_export_arguments("/tmp/x.glb", materials=False, tangents=True)
check(arguments["export_materials"] == "PLACEHOLDER" and arguments["export_tangents"] is True,
      "Materials off and tangents on are passed through")

check("no option named" in ex.exporter_problem(),
      "Unknown exporter options are named instead of failing vaguely")
check("export_cameras" in ex.exporter_problem() and "update" in ex.exporter_problem(),
      "The message names the option and says GEPrep needs an update")
gltf_properties.update(arguments)
check(ex.exporter_problem() == "", "No problem is reported when every option exists")
fake_bpy.ops.export_scene.gltf = SimpleNamespace(
    get_rna_type=lambda: (_ for _ in ()).throw(RuntimeError("missing")))
check("Enable Blender's glTF 2.0 exporter" in ex.exporter_problem(),
      "A disabled exporter is reported")

# ------------------------------------------------------------ messages
check([ex.format_size(n) for n in (0, 1023, 1024, 1536, 5 * 1024 * 1024)]
      == ["0 B", "1023 B", "1.0 KB", "1.5 KB", "5.0 MB"], "File sizes are readable")

inspection = {"materials": [
    {"status": "PASSED", "message": "", "textures": []},
    {"status": "FAILED", "message": "line one\nline two", "textures": [
        {"failures": ["Image file not found: /a.png"]},
        {"failures": []},
        {"failures": ["The image has no file path"]}]},
    {"status": "FAILED", "message": "UV map 'X' is missing", "textures": []},
    {"status": "INSPECT", "message": "ignored", "textures": []}]}
notes = ex.material_failure_notes("Wall", inspection)
check(notes == ["Wall: Image file not found: /a.png", "Wall: The image has no file path",
                "Wall: UV map 'X' is missing"],
      "Failed textures are listed, with the material message as a fallback")
check(ex.summarize_notes(notes) == "\n".join(notes), "Few notes are all shown")
many = [f"n{i}" for i in range(7)]
check(ex.summarize_notes(many) == "n0\nn1\nn2\nand 4 more", "Many notes are cut with a count")
check(many == [f"n{i}" for i in range(7)], "Summarizing does not change the list")



# ---------------------------------------------------- expected refusals
check(issubclass(ex.ExportBlockedError, ValueError), "A blocked export is still a ValueError")
try:
    ex.export_glb_job(SimpleNamespace(window=None), [], "x.glb", "SEPARATE", 1.0,
                      materials=True, tangents=False, overwrite=False)
    raise AssertionError("no error")
except ex.ExportBlockedError as error:
    check("window" in str(error), "No window raises the expected-refusal error")
try:
    ex.export_glb_job(SimpleNamespace(window=object()), [fake_object(type="CURVE")], "x.glb",
                      "SEPARATE", 1.0, materials=True, tangents=False, overwrite=False)
    raise AssertionError("no error")
except ex.ExportBlockedError as error:
    check("not a mesh" in str(error), "A blocked object raises the expected-refusal error")

print("ALL EXPORT LOGIC TESTS PASSED")

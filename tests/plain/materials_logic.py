"""Plain-Python tests for operations/materials.py (no Blender needed).

Run from the folder that contains the `geprep` package:
    python3 tests/materials_logic.py

Blender is replaced by small fakes. The fake Mesh.materials.pop() shifts
face indices like Blender does but does NOT shift object-level slot
materials, which is why restore_material_links() is needed afterwards.
"""

import importlib.util
import os
import sys
import tempfile
import types

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "geprep")


# ---------------------------------------------------------------- loading
fake_bpy = types.ModuleType("bpy")
fake_bpy.path = types.SimpleNamespace(
    abspath=lambda path, library=None: path,
)
sys.modules["bpy"] = fake_bpy

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


helpers = load("geprep.helpers.objects", "helpers/objects.py")
mat = load("geprep.operations.materials", "operations/materials.py")


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


# ------------------------------------------------------------------ fakes
class Named:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f"<{self.name}>"


class Material(Named):
    def __init__(self, name, node_tree=None):
        super().__init__(name)
        self.node_tree = node_tree
        self.use_nodes = True


class Collection(list):
    def get(self, name):
        return next((item for item in self if item.name == name), None)


class Sockets(list):
    def get(self, name):
        return next((item for item in self if item.name == name), None)


class Link:
    def __init__(self, from_node, from_socket, to_node, to_socket):
        self.from_node = from_node
        self.from_socket = from_socket
        self.to_node = to_node
        self.to_socket = to_socket
        from_socket.links.append(self)
        to_socket.links.append(self)


class Socket(Named):
    def __init__(self, name):
        super().__init__(name)
        self.identifier = name
        self.type = "RGBA"
        self.links = []

    @property
    def is_linked(self):
        return bool(self.links)


class Node(Named):
    def __init__(self, node_type, name, inputs=(), outputs=(), **extra):
        super().__init__(name)
        self.type = node_type
        self.inputs = Sockets(Socket(item) for item in inputs)
        self.outputs = Sockets(Socket(item) for item in outputs)
        self.node_tree = None
        self.image = None
        self.is_active_output = True
        self.from_instancer = False
        self.uv_map = ""
        self.space = "TANGENT"
        self.__dict__.update(extra)


class NodeTree:
    def __init__(self, *nodes):
        self.nodes = Collection(nodes)


class ColorSpace:
    def __init__(self, name, is_data):
        self.name = name
        self.is_data = is_data


class Image(Named):
    def __init__(self, name, path="", size=(256, 256), colorspace="sRGB",
                 source="FILE", packed=False):
        super().__init__(name)
        self.filepath = path
        self.size = size
        self.source = source
        self.library = None
        self.packed_file = object() if packed else None
        self.packed_files = []
        self.has_data = True
        self.is_dirty = False
        self.is_multiview = False
        self.colorspace_settings = ColorSpace(
            colorspace,
            colorspace == "Non-Color",
        )


class Polygons:
    def __init__(self, indices):
        self.indices = list(indices)

    def __len__(self):
        return len(self.indices)

    def foreach_get(self, attribute, buffer):
        assert attribute == "material_index"
        buffer[:] = type(buffer)("i", self.indices)

    def foreach_set(self, attribute, values):
        assert attribute == "material_index"
        self.indices = list(values)


class Mesh:
    def __init__(self, materials, face_indices):
        self.polygons = Polygons(face_indices)
        self.materials = MeshMaterials(self, materials)
        self.uv_layers = Collection()
        self.users = 1
        self.use_fake_user = False
        self.is_editable = True
        self.fail_update = 0

    def update(self):
        if self.fail_update:
            self.fail_update -= 1
            raise RuntimeError("injected update failure")


class MeshMaterials(list):
    def __init__(self, mesh, items):
        super().__init__(items)
        self.mesh = mesh
        self.object = None

    def pop(self, index=-1):
        removed = super().pop(index)

        # Blender shifts the face indices...
        self.mesh.polygons.indices = [
            value - 1 if value > index else value
            for value in self.mesh.polygons.indices
        ]
        # ...but only truncates object-level slot data.
        self.object.resize_slots(len(self))
        return removed

    def append(self, material):
        super().append(material)
        self.object.resize_slots(len(self))

    def clear(self):
        super().clear()
        self.object.resize_slots(0)


class Slot:
    def __init__(self, obj, index):
        self.obj = obj
        self.index = index

    @property
    def link(self):
        return self.obj.links[self.index]

    @link.setter
    def link(self, value):
        self.obj.links[self.index] = value

    @property
    def material(self):
        if self.link == "OBJECT":
            return self.obj.object_materials[self.index]
        return self.obj.data.materials[self.index]

    @material.setter
    def material(self, value):
        if self.link == "OBJECT":
            self.obj.object_materials[self.index] = value
        else:
            self.obj.data.materials[self.index] = value


class Obj(Named):
    def __init__(self, name, mesh):
        super().__init__(name)
        self.data = mesh
        mesh.materials.object = self
        self.links = ["DATA"] * len(mesh.materials)
        self.object_materials = [None] * len(mesh.materials)
        self.modifiers = []
        self.is_editable = True
        self.override_library = None
        self.active_material_index = 0

    def resize_slots(self, count):
        self.links = (self.links + ["DATA"] * count)[:count]
        self.object_materials = (self.object_materials + [None] * count)[:count]

    @property
    def material_slots(self):
        return [Slot(self, index) for index in range(len(self.data.materials))]


def make_object(slot_materials, face_indices, name="Obj"):
    mesh = Mesh(slot_materials, face_indices)
    return Obj(name, mesh)


def snapshot(obj):
    return (
        list(obj.data.materials),
        list(obj.data.polygons.indices),
        list(obj.links),
        list(obj.object_materials),
        obj.active_material_index,
    )


A, B, C, X = (Material(n) for n in "ABCX")

# ------------------------------------------------- slot removal: basics
obj = make_object([A, None, B, None], [0, 2, 3, 0, 2], "Basic")
obj.active_material_index = 2
count, message = mat.remove_empty_material_slots(obj)
check(count == 1, "One unused empty slot is removed")
check("Kept 1" in message, "The empty slot used by a face is reported as kept")
check(list(obj.data.materials) == [A, B, None], "Remaining slots keep their order")
check(obj.data.polygons.indices == [0, 1, 2, 0, 1],
      "Face assignments follow their slots")
check(obj.active_material_index == 1, "The active slot still points at B")

obj = make_object([A, B], [0, 1])
count, message = mat.remove_empty_material_slots(obj)
check(count == 0 and message == "No empty material slots",
      "Nothing is removed when no slot is empty")

obj = make_object([A, None], [0, 1])
count, message = mat.remove_empty_material_slots(obj)
check(count == 0 and "used by faces" in message,
      "Empty slots used by faces are never removed")

obj = make_object([None, None, A], [2, 2])
obj.active_material_index = 1
count, _ = mat.remove_empty_material_slots(obj)
check(count == 2 and list(obj.data.materials) == [A]
      and obj.data.polygons.indices == [0, 0]
      and obj.active_material_index == 0,
      "Several empty slots go at once and the active slot stays valid")

# ------------------------------------------- slot removal: object links
obj = make_object([None, A, None], [1, 1])
obj.links[2] = "OBJECT"
obj.object_materials[2] = C          # empty in the mesh, filled on the object
count, _ = mat.remove_empty_material_slots(obj)
check(count == 1 and obj.object_materials == [None, C],
      "An object-level material in a slot makes it non-empty and is kept")

obj = make_object([None, A, B], [1, 2])
obj.links[1] = "OBJECT"
obj.object_materials[1] = X          # hidden mesh material A stays untouched
obj.links[2] = "OBJECT"
obj.object_materials[2] = C
count, _ = mat.remove_empty_material_slots(obj)
check(count == 1, "A slot before object-linked slots is removed")
check(obj.links == ["OBJECT", "OBJECT"]
      and obj.object_materials == [X, C],
      "Object-linked slots keep link and material after the slots shift")
check(list(obj.data.materials) == [A, B], "Hidden mesh materials are kept")

obj = make_object([A, None], [0, 0])
obj.links[1] = "OBJECT"
obj.data.materials[1] = B           # object slot empty, mesh slot filled
count, _ = mat.remove_empty_material_slots(obj)
check(count == 0, "A mesh material hidden behind an object link is not deleted")

# ------------------------------------------------------ slot removal: guards
obj = make_object([A, None], [0])
obj.data.users = 2
count, message = mat.remove_empty_material_slots(obj)
check(count == 0 and "shared" in message, "Shared mesh data is left alone")

obj = make_object([A, None], [0])
obj.data.users, obj.data.use_fake_user = 2, True
count, _ = mat.remove_empty_material_slots(obj)
check(count == 1, "A fake user does not count as sharing")

obj = make_object([A, None], [0])
obj.modifiers = [types.SimpleNamespace(show_viewport=True)]
count, message = mat.remove_empty_material_slots(obj)
check(count == 0 and "modifiers" in message, "Enabled modifiers block removal")

obj = make_object([A, None], [0])
obj.modifiers = [types.SimpleNamespace(show_viewport=False)]
check(mat.remove_empty_material_slots(obj)[0] == 1, "Disabled modifiers do not")

for attribute, text in (("is_editable", "cannot be edited"),
                        ("override_library", "override")):
    obj = make_object([A, None], [0])
    setattr(obj, attribute, False if attribute == "is_editable" else object())
    count, message = mat.remove_empty_material_slots(obj)
    check(count == 0 and text in message, f"Blocked: {text}")

obj = make_object([A, None], [0])
obj.data.is_editable = False
check("mesh cannot be edited" in mat.remove_empty_material_slots(obj)[1],
      "A read-only mesh is left alone")

obj = make_object([A, None], [0, 5])
before = snapshot(obj)
count, message = mat.remove_empty_material_slots(obj)
check(count == 0 and "missing material slot 6" in message and snapshot(obj) == before,
      "A face pointing at a missing slot stops removal without changes")

# ---------------------------------------------------- slot removal: rollback
obj = make_object([A, None, B], [0, 2, 0])
obj.links[2] = "OBJECT"
obj.object_materials[2] = X
obj.active_material_index = 2
before = snapshot(obj)
obj.data.fail_update = 1             # fails once, right after the pops
try:
    mat.remove_empty_material_slots(obj)
    raise SystemExit("expected failure")
except RuntimeError as error:
    check("injected" in str(error), "The original error is raised")
check(snapshot(obj) == before,
      "A failed removal restores materials, faces, links and active slot")

obj = make_object([A, None, B], [0, 2, 0])
obj.data.fail_update = 2             # the rollback fails as well
try:
    mat.remove_empty_material_slots(obj)
    raise SystemExit("expected failure")
except mat.MaterialSlotCommitError as error:
    check("Undo" in str(error), "A failed rollback asks for Undo")


# ---------------------------------------------------------- pure helpers
check(mat.worst_status(["PASSED", "INSPECT"]) == "INSPECT"
      and mat.worst_status(["INSPECT", "FAILED", "PASSED"]) == "FAILED"
      and mat.worst_status([]) == "PASSED", "worst_status picks the most serious")
check([mat.is_power_of_two(n) for n in (0, 1, 3, 256, 1000, 4096)]
      == [False, True, False, True, False, True], "Power of two detection")
check(mat.duplicate_image_base("wall.001", {"wall"}) == "wall"
      and mat.duplicate_image_base("wall.001", set()) == ""
      and mat.duplicate_image_base("wall.v2", {"wall"}) == "",
      "Copies are recognised by a .001 suffix only when the original exists")


# ---------------------------------------------------- inspection helpers
def principled():
    return Node("BSDF_PRINCIPLED", "Principled", inputs=(
        "Base Color", "Roughness", "Metallic", "Emission Color", "Normal"))


def output():
    return Node("OUTPUT_MATERIAL", "Output", inputs=("Surface", "Displacement"))


def image_node(image, name="Image"):
    return Node("TEX_IMAGE", name, inputs=("Vector",), outputs=("Color", "Alpha"),
                image=image)


def uv_source(layer_name=""):
    return Node("UVMAP", "UVMap", outputs=("UV",), uv_map=layer_name)


def connect(source, source_socket, target, target_socket):
    return Link(
        source,
        source.outputs.get(source_socket),
        target,
        target.inputs.get(target_socket),
    )


def textured_object(image, target_socket, *, with_uv=True, uv_map="",
                    connect_vector=True):
    tex, bsdf = image_node(image), principled()
    nodes = [tex, bsdf, output()]
    connect(tex, "Color", bsdf, target_socket)

    if connect_vector:
        uv = uv_source(uv_map)
        nodes.append(uv)
        connect(uv, "UV", tex, "Vector")

    material = Material("Mat", NodeTree(*nodes))
    obj = make_object([material], [0, 0], "Tex")

    if with_uv:
        obj.data.uv_layers.append(Named("UVMap"))

    return obj


def inspect(obj, **kwargs):
    kwargs.setdefault("image_cache", {})
    return mat.inspect_object_materials(obj, **kwargs)


def first_texture(result):
    return result["materials"][0]["textures"][0]


with tempfile.TemporaryDirectory() as folder:
    real = os.path.join(folder, "albedo.png")
    open(real, "wb").close()

    # A correct setup has no findings.
    good = textured_object(Image("albedo", real), "Base Color")
    result = inspect(good)
    check(result["status"] == "PASSED" and result["image_count"] == 1
          and result["material_count"] == 1 and result["empty_slots"] == 0,
          "A correct textured material has no findings")

    # Image file problems.
    missing = textured_object(Image("gone", os.path.join(folder, "none.png")),
                              "Base Color")
    texture = first_texture(inspect(missing))
    check(texture["status"] == "FAILED" and "not found" in texture["message"],
          "A missing image file fails")
    check("size is unavailable" not in texture["message"],
          "A missing file does not also report an unavailable size")

    nopath = textured_object(Image("nopath", ""), "Base Color")
    check(first_texture(inspect(nopath))["status"] == "FAILED",
          "An image with no file path fails")

    packed = textured_object(Image("packed", "", packed=True), "Base Color")
    check(first_texture(inspect(packed))["status"] == "PASSED"
          and first_texture(inspect(packed))["storage"] == "Packed",
          "A packed image needs no file")

    # Size findings.
    odd = textured_object(Image("odd", real, size=(300, 256)), "Base Color")
    check("power of two" in first_texture(inspect(odd))["message"],
          "A non power-of-two image is reported")

    big = textured_object(Image("big", real, size=(8192, 8192)), "Base Color")
    check("Larger than 4096" in first_texture(inspect(big))["message"],
          "A texture above the maximum size is reported")
    check("Larger than" not in first_texture(inspect(big, max_size=8192))["message"],
          "The maximum size can be raised")

    copy = textured_object(Image("albedo.001", real), "Base Color")
    check("copy of 'albedo'" in first_texture(
        inspect(copy, image_names=frozenset({"albedo", "albedo.001"})))["message"],
          "A duplicated image is reported")

    # Color space against use.
    rough = textured_object(Image("r", real, colorspace="sRGB"), "Roughness")
    check("Roughness" in first_texture(inspect(rough))["message"]
          and "Non-Color" in first_texture(inspect(rough))["message"],
          "A roughness map set to sRGB is reported")

    rough_ok = textured_object(Image("r", real, colorspace="Non-Color"), "Roughness")
    check(first_texture(inspect(rough_ok))["status"] == "PASSED",
          "A roughness map set to Non-Color passes")

    wrong = textured_object(Image("c", real, colorspace="Non-Color"), "Base Color")
    check("Base Color but set to Non-Color" in first_texture(inspect(wrong))["message"],
          "A color map set to Non-Color is reported")

    # A color map routed through a reroute still counts as color.
    tex, reroute, bsdf = image_node(Image("c", real)), Node(
        "REROUTE", "Reroute", inputs=("Input",), outputs=("Output",)), principled()
    uv = uv_source()
    connect(tex, "Color", reroute, "Input")
    connect(reroute, "Output", bsdf, "Base Color")
    connect(uv, "UV", tex, "Vector")
    through = make_object([Material("M", NodeTree(tex, reroute, bsdf, output(), uv))], [0])
    through.data.uv_layers.append(Named("UVMap"))
    check(first_texture(inspect(through))["status"] == "PASSED",
          "A reroute between the image and the shader is followed")

    # Normal map: image into a Normal Map node.
    tex = image_node(Image("n", real, colorspace="sRGB"))
    normal = Node("NORMAL_MAP", "NormalMap", inputs=("Color",), outputs=("Normal",))
    uv = uv_source()
    connect(tex, "Color", normal, "Color")
    connect(uv, "UV", tex, "Vector")
    mesh_obj = make_object([Material("M", NodeTree(tex, normal, output(), uv))], [0])
    mesh_obj.data.uv_layers.append(Named("UVMap"))
    check("Normal Map" in first_texture(inspect(mesh_obj))["message"],
          "A normal map set to sRGB is reported")

    # Unconnected image node.
    lone = image_node(Image("lone", real))
    lone_obj = make_object([Material("M", NodeTree(lone, output()))], [0])
    lone_obj.data.uv_layers.append(Named("UVMap"))
    check("not connected" in first_texture(inspect(lone_obj))["message"],
          "An image node that feeds nothing is reported")

    # UV problems.
    check(first_texture(inspect(textured_object(
        Image("a", real), "Base Color", with_uv=False)))["status"] == "FAILED",
        "A UV Map node on a mesh without UVs fails")
    check("'Other' is missing" in first_texture(inspect(textured_object(
        Image("a", real), "Base Color", uv_map="Other")))["message"],
        "A UV Map node pointing at a missing map fails")
    check(first_texture(inspect(textured_object(
        Image("a", real), "Base Color", with_uv=False, connect_vector=False)))
        ["status"] == "FAILED",
        "A texture with no vector input on a mesh without UVs fails")
    check(first_texture(inspect(textured_object(
        Image("a", real), "Base Color", connect_vector=False)))["status"] == "PASSED",
        "A texture with no vector input uses the default UVs")

    # Node groups: textures inside are found, cycles do not hang.
    inner_tex = image_node(Image("inner", real))
    inner_bsdf = principled()
    connect(inner_tex, "Color", inner_bsdf, "Base Color")
    inner_uv = uv_source()
    connect(inner_uv, "UV", inner_tex, "Vector")
    inner_tree = NodeTree(inner_tex, inner_bsdf, inner_uv)
    group = Node("GROUP", "Group")
    group.node_tree = inner_tree
    loop = Node("GROUP", "Loop")
    loop.node_tree = inner_tree
    inner_tree.nodes.append(loop)        # the tree contains itself
    grouped = make_object([Material("M", NodeTree(group, output()))], [0])
    grouped.data.uv_layers.append(Named("UVMap"))
    result = inspect(grouped)
    check(first_texture(result)["node_path"] == "Group / Image"
          and result["image_count"] == 1,
          "Textures inside node groups are found, and group cycles end")

    # Procedural and node-less materials.
    noise = Node("TEX_NOISE", "Noise", outputs=("Color",))
    procedural = make_object([Material("M", NodeTree(noise, output()))], [0])
    check("procedural" in inspect(procedural)["materials"][0]["message"],
          "A procedural texture is reported")
    check("no node tree" in inspect(make_object(
        [Material("M")], [0]))["materials"][0]["message"],
        "A material without a node tree is reported")
    no_output = make_object([Material("M", NodeTree(principled()))], [0])
    check("No active Material Output" in inspect(no_output)["materials"][0]["message"],
          "A missing Material Output is reported")

# ------------------------------------------------------- slot-level findings
obj = make_object([A, None, B, None], [0, 2, 3])
result = inspect(obj)
messages = [entry["message"] for entry in result["materials"]]
check(result["empty_slots"] == 2, "Every empty slot is counted, used by faces or not")
check("faces use this slot" in messages[1], "An unused empty slot says it can be removed")
check("faces use this slot" in messages[3] or "No material assigned" in messages[3],
      "An empty slot used by faces is reported")
check(messages[1] != messages[3], "Used and unused empty slots read differently")

obj = make_object([A, B], [0, 0])
result = inspect(obj)
check("No faces use this slot" in result["materials"][1]["message"],
      "A filled slot that no face uses is reported")

obj = make_object([A, None], [])
messages = [entry["message"] for entry in inspect(obj)["materials"]]
check("No faces use this slot" in messages[0] and "no faces use this slot" in messages[1],
      "On a mesh without faces every slot is reported as unused")

obj = make_object([], [0])
check("No material slots" in inspect(obj)["message"], "An object without slots is reported")

obj = make_object([A], [0])
obj.modifiers = [types.SimpleNamespace(show_viewport=True)]
check("modifiers" in inspect(obj)["message"], "Enabled modifiers are mentioned")

obj = make_object([A], [0, 3])
check("missing material slot(s): 4" in inspect(obj)["message"],
      "Faces using a missing slot are reported")

# ------------------------------------- hidden mesh material behind a slot
obj = make_object([A, B], [1, 1], "Hidden")
obj.links[0] = "OBJECT"                # object slot empty, mesh slot holds A
result = inspect(obj)
message = result["materials"][0]["message"]
check("'A' in this slot" in message and "kept" in message,
      "A hidden mesh material is explained instead of offered for deletion")
check("can delete" not in message and result["empty_slots"] == 0,
      "A slot with a hidden mesh material is not counted or advertised as empty")
before = snapshot(obj)
count, _ = mat.remove_empty_material_slots(obj)
check(count == 0 and snapshot(obj) == before,
      "Removal keeps the slot with the hidden material")

obj = make_object([A, B], [0, 0], "HiddenUsed")
obj.links[1] = "OBJECT"
check("'B' in this slot" in inspect(obj)["materials"][1]["message"],
      "The explanation also appears when faces use the slot")


# ------------------------------------ blockers only matter when removing
obj = make_object([A, B], [0, 1], "SharedNoEmpty")
obj.data.users = 3
check(mat.remove_empty_material_slots(obj)[1] == "No empty material slots",
      "A shared mesh with nothing to remove says there is nothing to remove")
obj = make_object([A, None], [0, 0], "SharedEmpty")
obj.data.users = 3
check("shared" in mat.remove_empty_material_slots(obj)[1],
      "A shared mesh with something to remove still explains why it is skipped")


# ---------------------------------------- unclassified color-space paths
def graph_object(image, *, direct=(), through=(), extra_uv=True):
    """Image feeding `direct` Principled inputs, and `through` ColorRamp ones."""
    tex, bsdf = image_node(image), principled()
    ramp = Node("VALTORGB", "ColorRamp", inputs=("Fac",), outputs=("Color",))
    nodes = [tex, bsdf, ramp, output()]

    for socket in direct:
        connect(tex, "Color", bsdf, socket)

    for socket in through:
        connect(tex, "Color", ramp, "Fac")
        connect(ramp, "Color", bsdf, socket)

    uv = uv_source()
    connect(uv, "UV", tex, "Vector")
    nodes.append(uv)
    obj = make_object([Material("M", NodeTree(*nodes))], [0])
    obj.data.uv_layers.append(Named("UVMap"))
    return obj


with tempfile.TemporaryDirectory() as folder:
    real = os.path.join(folder, "t.png")
    open(real, "wb").close()

    # Roughness is recognised, the ColorRamp path is not.
    texture = first_texture(inspect(graph_object(
        Image("t", real, colorspace="Non-Color"),
        direct=["Roughness"], through=["Base Color"])))
    check("Also feeds ColorRamp" in texture["message"],
          "A recognised path no longer hides an unrecognised one")

    # Only the unrecognised path: say where it goes.
    texture = first_texture(inspect(graph_object(
        Image("t", real), through=["Base Color"])))
    check("Cannot tell" in texture["message"] and "ColorRamp" in texture["message"],
          "A fully unrecognised path names the node it goes through")

    # Principled inputs we do not classify count as unresolved too.
    texture = first_texture(inspect(graph_object(
        Image("t", real), direct=["Base Color", "Normal"])))
    check("Principled / Normal" in texture["message"],
          "An unclassified Principled input is named")

    # Fully recognised graphs stay quiet.
    check(first_texture(inspect(graph_object(
        Image("t", real), direct=["Base Color"])))["status"] == "PASSED",
        "A fully recognised graph raises nothing extra")

    # One image used for color and data.
    for space in ("sRGB", "Non-Color"):
        texture = first_texture(inspect(graph_object(
            Image("t", real, colorspace=space),
            direct=["Base Color", "Roughness"])))
        check("can't be both" in texture["message"]
              and "Base Color" in texture["message"]
              and "Roughness" in texture["message"],
              f"Color and data use of one image is explained ({space})")
        check("Usually needs Non-Color" not in texture["message"]
              and "set to Non-Color. Check" not in texture["message"],
              f"The conflict replaces the single-setting advice ({space})")


# ------------------------------------- groups and color-preserving nodes
def finish(nodes):
    obj = make_object([Material("M", NodeTree(*nodes))], [0], "Route")
    obj.data.uv_layers.append(Named("UVMap"))
    return obj


def image_in_group(image, socket="Color"):
    tex, uv = image_node(image), uv_source()
    group_output = Node("GROUP_OUTPUT", "Group Output", inputs=(socket,))
    connect(uv, "UV", tex, "Vector")
    connect(tex, "Color", group_output, socket)
    return NodeTree(tex, uv, group_output)


def group_node(name, tree, inputs=(), outputs=("Color",)):
    node = Node("GROUP", name, inputs=inputs, outputs=outputs)
    node.node_tree = tree
    return node


def messages_for(obj, **kwargs):
    return [t["message"] for m in inspect(obj, **kwargs)["materials"]
            for t in m["textures"]]


with tempfile.TemporaryDirectory() as folder:
    real = os.path.join(folder, "t.png")
    open(real, "wb").close()

    # Image inside a group, group output feeds Base Color outside.
    for space, expect in (("Non-Color", "Base Color but set to Non-Color"),
                          ("sRGB", None)):
        group = group_node("G", image_in_group(Image("t", real, colorspace=space)))
        bsdf = principled()
        connect(group, "Color", bsdf, "Base Color")
        message = messages_for(finish([group, bsdf, output()]))[0]
        check((expect in message) if expect else message == "",
              f"Image inside a group feeding Base Color outside ({space})")

    # Image outside, group input feeds Roughness inside.
    tex, uv = image_node(Image("t", real)), uv_source()
    group_input = Node("GROUP_INPUT", "Group Input", outputs=("Color",))
    inner_bsdf = principled()
    connect(group_input, "Color", inner_bsdf, "Roughness")
    group = group_node("G", NodeTree(group_input, inner_bsdf),
                       inputs=("Color",), outputs=())
    connect(uv, "UV", tex, "Vector")
    connect(tex, "Color", group, "Color")
    message = messages_for(finish([tex, uv, group, output()]))[0]
    check("Roughness" in message and "Non-Color" in message,
          "Image outside a group feeding Roughness inside it")

    # Two levels of groups.
    inner = group_node("Inner", image_in_group(Image("t", real, colorspace="Non-Color")))
    outer_output = Node("GROUP_OUTPUT", "Outer Output", inputs=("Color",))
    connect(inner, "Color", outer_output, "Color")
    outer = group_node("Outer", NodeTree(inner, outer_output))
    bsdf = principled()
    connect(outer, "Color", bsdf, "Base Color")
    check("Base Color but set to Non-Color" in messages_for(
        finish([outer, bsdf, output()]))[0],
        "A path through two nested groups is followed out")

    # One group used twice: each copy only reports its own destination.
    shared = image_in_group(Image("t", real, colorspace="Non-Color"))
    first, second = group_node("First", shared), group_node("Second", shared)
    bsdf = principled()
    connect(first, "Color", bsdf, "Base Color")      # Second goes nowhere
    result = inspect(finish([first, second, bsdf, output()]))
    textures = {t["node_path"].split(" / ")[0]: t["message"]
                for t in result["materials"][0]["textures"]}
    check("Base Color but set to Non-Color" in textures["First"],
          "The first copy of a shared group reports its destination")
    check("Base Color" not in textures["Second"],
          "The second copy is not given the first copy's destination")

    # Group sockets pair up by identifier, not by name.
    group = group_node("G", image_in_group(
        Image("t", real, colorspace="Non-Color"), "Inside Name"),
        outputs=("Outside Name",))
    group.outputs[0].identifier = "Socket_7"
    group.node_tree.nodes[2].inputs[0].identifier = "Socket_7"
    bsdf = principled()
    connect(group, "Outside Name", bsdf, "Base Color")
    check("Base Color but set to Non-Color" in messages_for(
        finish([group, bsdf, output()]))[0],
        "Group sockets are matched by identifier when the names differ")

    # A group without a node tree stays unresolved.
    tex, uv = image_node(Image("t", real)), uv_source()
    group = group_node("Empty", None, inputs=("Color",), outputs=())
    connect(uv, "UV", tex, "Vector")
    connect(tex, "Color", group, "Color")
    check("Cannot tell" in messages_for(finish([tex, uv, group, output()]))[0],
          "A group with no node tree is reported, not guessed")

    # Nodes that keep a color are followed...
    def through(node_type, in_socket, out_socket, target, space="Non-Color",
                socket_type="RGBA"):
        tex, uv = image_node(Image("t", real, colorspace=space)), uv_source()
        node = Node(node_type, node_type.title(),
                    inputs=("Factor", "Color", "A", "B", "Gamma"),
                    outputs=(out_socket,))
        node.inputs.get(in_socket).type = socket_type
        bsdf = principled()
        connect(uv, "UV", tex, "Vector")
        connect(tex, "Color", node, in_socket)
        connect(node, out_socket, bsdf, target)
        return messages_for(finish([tex, uv, node, bsdf, output()]))[0]

    check("Base Color but set to Non-Color" in through("INVERT", "Color", "Color", "Base Color"),
          "A color through Invert is followed")
    check("Base Color but set to Non-Color" in through("MIX", "A", "Result", "Base Color"),
          "A color into a Mix color input is followed")
    check("Roughness" in through("HUE_SAT", "Color", "Color", "Roughness", "sRGB"),
          "A color through Hue/Saturation is followed")

    # ...but a Factor input or a value-to-color node is not.
    message = through("MIX", "Factor", "Result", "Base Color")
    check("Cannot tell" in message and "Mix" in message and "Base Color but" not in message,
          "A mask used as a Mix factor is not mistaken for a color")
    message = through("GAMMA", "Gamma", "Color", "Base Color")
    check("Cannot tell" in message and "Base Color but" not in message,
          "A value used as a Gamma amount is not mistaken for a color")

    # A Mix node set to numbers or vectors is not a color path.
    for kind in ("VALUE", "VECTOR"):
        message = through("MIX", "A", "Result", "Base Color", socket_type=kind)
        check("Cannot tell" in message and "Base Color but" not in message,
              f"A Mix input that is not a color is not followed ({kind})")

    # Packed maps: R, G, B hold different data.
    def packed(space, separator="SEPARATE_COLOR", routes=(("Green", "Roughness"),
               ("Blue", "Metallic")), also_direct=()):
        tex, uv = image_node(Image("orm", real, colorspace=space)), uv_source()
        input_name = "Color" if separator == "SEPARATE_COLOR" else "Image"
        split = Node(separator, "Split", inputs=(input_name,),
                     outputs=("Red", "Green", "Blue"))
        bsdf = principled()
        connect(uv, "UV", tex, "Vector")
        connect(tex, "Color", split, input_name)
        for channel, socket in routes:
            connect(split, channel, bsdf, socket)
        for socket in also_direct:
            connect(tex, "Color", bsdf, socket)
        return messages_for(finish([tex, uv, split, bsdf, output()]))[0]

    for separator in ("SEPARATE_COLOR", "SEPRGB"):
        message = packed("sRGB", separator)
        check("Roughness" in message and "Metallic" in message
              and "Non-Color" in message,
              f"A packed map on sRGB is reported for its data channels ({separator})")
        check(packed("Non-Color", separator) == "",
              f"A packed map on Non-Color has no findings ({separator})")

    message = packed("sRGB", routes=(("Green", "Base Color"),))
    check("Cannot tell" in message and "one channel" in message
          and "Base Color but" not in message,
          "A single channel reaching Base Color is reported as unresolved")

    message = packed("Non-Color", routes=(("Green", "Emission Color"),))
    check("one channel" in message, "The same holds for Emission")

    message = packed("sRGB", also_direct=("Base Color",))
    check("can't be both" in message and "Base Color" in message,
          "A map used packed and as a color is reported as a conflict")

    message = packed("sRGB", routes=(("Green", "Roughness"), ("Red", "Base Color")))
    check("Roughness" in message and "Also feeds" in message and "one channel" in message,
          "A known data path and an ambiguous channel are both mentioned")


print("ALL MATERIAL LOGIC TESTS PASSED")

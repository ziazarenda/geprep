exec("""
import uuid

import bpy
from geprep.operations import materials as mat_ops
from geprep.operators.materials import run_material_check


context = bpy.context
prefix = f"GEPrep_MatTest_{uuid.uuid4().hex[:8]}"
made_objects = []
made_meshes = []
made_materials = []
made_images = []
made_groups = []


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def make_material(name):
    material = bpy.data.materials.new(f"{prefix}_{name}")
    made_materials.append(material)
    if not material.node_tree:
        material.use_nodes = True
    return material


def make_object(name, materials, face_slots):
    # One quad per entry in face_slots, laid out in a row.
    vertices, faces = [], []
    for index in range(len(face_slots)):
        x = index * 2.0
        base = len(vertices)
        vertices += [(x, 0, 0), (x + 1, 0, 0), (x + 1, 1, 0), (x, 1, 0)]
        faces.append((base, base + 1, base + 2, base + 3))
    mesh = bpy.data.meshes.new(f"{prefix}_{name}")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    for material in materials:
        mesh.materials.append(material)
    mesh.polygons.foreach_set("material_index", face_slots)
    mesh.uv_layers.new(name="UVMap")
    obj = bpy.data.objects.new(f"{prefix}_{name}", mesh)
    context.scene.collection.objects.link(obj)
    made_objects.append(obj)
    made_meshes.append(mesh)
    return obj


def face_slots(obj):
    return [polygon.material_index for polygon in obj.data.polygons]


try:
    A, B, C = make_material("A"), make_material("B"), make_material("C")

    info = bpy.types.Material.bl_rna.properties.get("use_nodes")
    print("INFO: Material.use_nodes exists:", info is not None,
          "| deprecated flag:", getattr(info, "is_deprecated", "n/a"))

    # ---- removal on the real API
    obj = make_object("Basic", [A, None, B, None], [0, 2, 3, 0])
    obj.active_material_index = 2
    count, message = mat_ops.remove_empty_material_slots(obj)
    check(count == 1, "One unused empty slot is removed")
    check([slot.material for slot in obj.material_slots] == [A, B, None],
          "Remaining slots keep their order")
    check(face_slots(obj) == [0, 1, 2, 0], "Face assignments follow their slots")
    check(obj.active_material_index == 1, "The active slot still points at B")
    check("Kept 1" in message, "The used empty slot is reported as kept")

    obj = make_object("ObjectLinked", [None, A, B], [1, 2])
    obj.material_slots[1].link = "OBJECT"
    obj.material_slots[1].material = C
    obj.material_slots[2].link = "OBJECT"
    obj.material_slots[2].material = A
    count, _ = mat_ops.remove_empty_material_slots(obj)
    slots = [(slot.link, slot.material) for slot in obj.material_slots]
    check(count == 1, "A slot in front of object-linked slots is removed")
    check(slots == [("OBJECT", C), ("OBJECT", A)],
          "Object-linked slots keep link and material after the shift")
    check([m for m in obj.data.materials] == [A, B],
          "Hidden mesh-level materials are kept")
    check(face_slots(obj) == [0, 1], "Faces still point at the same slots")

    obj = make_object("Shared", [A, None], [0, 0])
    twin = bpy.data.objects.new(f"{prefix}_SharedTwin", obj.data)
    context.scene.collection.objects.link(twin)
    made_objects.append(twin)
    count, message = mat_ops.remove_empty_material_slots(obj)
    check(count == 0 and "shared" in message, "Shared mesh data is left alone")
    check(len(obj.material_slots) == 2, "A shared mesh keeps its slots")

    obj = make_object("FakeUser", [A, None], [0, 0])
    obj.data.use_fake_user = True
    count, _ = mat_ops.remove_empty_material_slots(obj)
    check(count == 1, "A fake user does not count as sharing")

    obj = make_object("Nothing", [A, B], [0, 1])
    check(mat_ops.remove_empty_material_slots(obj)[0] == 0,
          "No empty slots means nothing to do")

    # ---- checks on real node trees
    image_a = bpy.data.images.new(f"{prefix}_wall", 300, 256)
    image_b = bpy.data.images.new(f"{prefix}_wall", 256, 256)   # becomes .001
    missing = bpy.data.images.new(f"{prefix}_missing", 64, 64)
    missing.source = "FILE"
    missing.filepath = "//definitely_not_here.png"
    made_images += [image_a, image_b, missing]
    check(image_b.name.endswith(".001"), "Blender names the second image .001")

    def textured(name, image, socket):
        material = make_material(name)
        tree = material.node_tree
        bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
        tex = tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tree.links.new(tex.outputs["Color"], bsdf.inputs[socket])
        return make_object(name, [material], [0])

    names = frozenset(image.name for image in bpy.data.images)

    def first_texture(obj, **kwargs):
        result = mat_ops.inspect_object_materials(
            obj, image_cache={}, image_names=names, **kwargs)
        return result, result["materials"][0]["textures"][0]

    result, texture = first_texture(textured("rough", image_a, "Roughness"))
    check("Roughness" in texture["message"] and "Non-Color" in texture["message"],
          "A roughness map left on sRGB is reported")
    check("power of two" in texture["message"],
          "A 300 x 256 generated image is reported as not a power of two")

    image_a.colorspace_settings.name = "Non-Color"
    result, texture = first_texture(textured("rough_ok", image_a, "Roughness"))
    check("Non-Color" not in texture["message"],
          "A roughness map on Non-Color has no color space finding")

    result, texture = first_texture(textured("copy", image_b, "Base Color"))
    check("copy of" in texture["message"], "A .001 image is reported as a possible copy")

    result, texture = first_texture(textured("gone", missing, "Base Color"))
    check(texture["status"] == "FAILED" and "not found" in texture["message"],
          "An image whose file is missing fails")
    check(result["status"] == "FAILED", "The object status follows its worst texture")

    # ---- color-space tracing across real node group boundaries
    srgb_image = bpy.data.images.new(f"{prefix}_srgb", 64, 64)
    data_image = bpy.data.images.new(f"{prefix}_data", 64, 64)
    data_image.colorspace_settings.name = "Non-Color"
    made_images += [srgb_image, data_image]
    names = frozenset(image.name for image in bpy.data.images)

    group = bpy.data.node_groups.new(f"{prefix}_out", "ShaderNodeTree")
    made_groups.append(group)
    group.interface.new_socket("Color", in_out="OUTPUT", socket_type="NodeSocketColor")
    inner_tex = group.nodes.new("ShaderNodeTexImage")
    inner_tex.image = data_image
    group_out = group.nodes.new("NodeGroupOutput")
    group.links.new(inner_tex.outputs["Color"], group_out.inputs["Color"])
    material = make_material("grouped_out")
    tree = material.node_tree
    bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
    node = tree.nodes.new("ShaderNodeGroup")
    node.node_tree = group
    tree.links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    result, texture = first_texture(make_object("grouped_out", [material], [0]))
    check("Base Color but set to Non-Color" in texture["message"],
          "An image inside a real node group is traced to Base Color outside it")

    group = bpy.data.node_groups.new(f"{prefix}_in", "ShaderNodeTree")
    made_groups.append(group)
    group.interface.new_socket("Color", in_out="INPUT", socket_type="NodeSocketColor")
    group_in = group.nodes.new("NodeGroupInput")
    inner_bsdf = group.nodes.new("ShaderNodeBsdfPrincipled")
    group.links.new(group_in.outputs["Color"], inner_bsdf.inputs["Roughness"])
    material = make_material("grouped_in")
    tree = material.node_tree
    tex = tree.nodes.new("ShaderNodeTexImage")
    tex.image = srgb_image
    node = tree.nodes.new("ShaderNodeGroup")
    node.node_tree = group
    tree.links.new(tex.outputs["Color"], node.inputs["Color"])
    result, texture = first_texture(make_object("grouped_in", [material], [0]))
    check("Roughness" in texture["message"] and "Non-Color" in texture["message"],
          "An image going into a real node group is traced to Roughness inside it")

    # ---- real Mix and Separate Color nodes
    def routed(name, image, build):
        material = make_material(name)
        tree = material.node_tree
        bsdf = next(n for n in tree.nodes if n.type == "BSDF_PRINCIPLED")
        tex = tree.nodes.new("ShaderNodeTexImage")
        tex.image = image
        build(tree, tex, bsdf)
        return first_texture(make_object(name, [material], [0]))[1]

    def socket(sockets, identifier):
        return next(item for item in sockets if item.identifier == identifier)

    def color_mix(tree, tex, bsdf):
        mix = tree.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        tree.links.new(tex.outputs["Color"], socket(mix.inputs, "A_Color"))
        tree.links.new(socket(mix.outputs, "Result_Color"), bsdf.inputs["Base Color"])

    def float_mix(tree, tex, bsdf):
        mix = tree.nodes.new("ShaderNodeMix")
        mix.data_type = "FLOAT"
        tree.links.new(tex.outputs["Color"], socket(mix.inputs, "A_Float"))
        tree.links.new(socket(mix.outputs, "Result_Float"), bsdf.inputs["Roughness"])

    def packed_roughness(tree, tex, bsdf):
        split = tree.nodes.new("ShaderNodeSeparateColor")
        tree.links.new(tex.outputs["Color"], split.inputs["Color"])
        tree.links.new(split.outputs["Green"], bsdf.inputs["Roughness"])

    def packed_color(tree, tex, bsdf):
        split = tree.nodes.new("ShaderNodeSeparateColor")
        tree.links.new(tex.outputs["Color"], split.inputs["Color"])
        tree.links.new(split.outputs["Green"], bsdf.inputs["Base Color"])

    texture = routed("mix_color", data_image, color_mix)
    check("Base Color but set to Non-Color" in texture["message"],
          "A color Mix node is followed to Base Color")
    texture = routed("mix_float", srgb_image, float_mix)
    check("Cannot tell" in texture["message"] and "Roughness but" not in texture["message"],
          "A number Mix node is not followed")
    texture = routed("packed_rough", srgb_image, packed_roughness)
    check("Roughness" in texture["message"] and "Non-Color" in texture["message"],
          "A packed map on sRGB is reported through a real Separate Color node")
    texture = routed("packed_color", srgb_image, packed_color)
    check("one channel" in texture["message"] and "Base Color but" not in texture["message"],
          "One channel into Base Color is reported as unresolved")

    # ---- object-level findings
    obj = make_object("Findings", [A, None, B], [0, 0, 0])
    result = mat_ops.inspect_object_materials(obj, image_cache={})
    messages = [entry["message"] for entry in result["materials"]]
    check(result["empty_slots"] == 1, "The empty slot is counted")
    check("Remove Empty" in messages[1] or "no faces" in messages[1].lower(),
          "An unused empty slot is described")
    check("No faces use this slot" in messages[2], "A filled but unused slot is reported")

    # ---- a hidden mesh material behind an object-linked slot
    obj = make_object("Hidden", [A, B], [1, 1])
    obj.material_slots[0].link = "OBJECT"       # object slot stays empty
    result = mat_ops.inspect_object_materials(obj, image_cache={})
    message = result["materials"][0]["message"]
    check(result["empty_slots"] == 0 and "can delete" not in message
          and A.name in message,
          "A hidden mesh material is explained, not offered for deletion")
    count, _ = mat_ops.remove_empty_material_slots(obj)
    check(count == 0 and len(obj.material_slots) == 2,
          "Removal keeps the slot with the hidden material")

    # ---- the stored results and the checker guard
    obj = make_object("Stored", [A], [0])
    guarded = make_object("Guarded", [B], [0])
    guarded.geprep_checker.active = True
    try:
        passed, inspect, failed = run_material_check(context, [obj, guarded])
        results = context.scene.geprep.material_results
        check(len(results) == 2, "Both objects get a stored result")
        check("checker" in results[1].message.lower() and results[1].status == "INSPECT",
              "An object with an active checker is not checked and says why")
        check(results[0].materials[0].name == A.name, "Slot results are stored")
    finally:
        guarded.geprep_checker.active = False
        context.scene.geprep.material_results.clear()

    # ---- the operators
    for item in context.selected_objects:
        item.select_set(False)
    obj = make_object("Operators", [A, None], [0, 0])
    obj.select_set(True)
    context.view_layer.objects.active = obj
    check(bpy.ops.geprep.check_materials() == {"FINISHED"}, "Check Materials runs")
    check(len(context.scene.geprep.material_results) == 1, "It stores one result")
    check(bpy.ops.geprep.remove_empty_material_slots() == {"FINISHED"},
          "Remove Empty Slots runs")
    check(len(obj.material_slots) == 1, "It removed the empty slot")
    check(context.scene.geprep.material_slot_results[0].status == "CHANGED",
          "The removal result says Changed")
    check(context.scene.geprep.material_results[0].empty_slots == 0,
          "The earlier check was refreshed after the removal")

    print("ALL MATERIAL TESTS PASSED")

finally:
    scene = context.scene
    scene.geprep.material_results.clear()
    scene.geprep.material_slot_results.clear()
    for obj in made_objects:
        bpy.data.objects.remove(obj, do_unlink=True)
    for mesh in made_meshes:
        mesh.use_fake_user = False
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    for material in made_materials:
        bpy.data.materials.remove(material)
    for image in made_images:
        bpy.data.images.remove(image)
    for group in made_groups:
        bpy.data.node_groups.remove(group)
    print("Temporary test data removed")
""")

exec("""
import uuid
from types import SimpleNamespace

import bpy
from geprep.operations import checker as checker_ops
from geprep.operations.uv import apply_uv_density


context = bpy.context
prefix = f"GEPrep_CheckerTest_{uuid.uuid4().hex[:8]}"
test_scene = bpy.data.scenes.new(prefix)
checker_names = set()
original_create = checker_ops.create_checker_material


def tracked_create(*args, **kwargs):
    material = original_create(*args, **kwargs)
    checker_names.add(material.name)
    return material


checker_ops.create_checker_material = tracked_create


def active_previews():
    return [
        obj for obj in bpy.data.objects
        if obj.name.startswith(prefix) and obj.geprep_checker.active
    ]


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def uv_coordinates(mesh):
    return [
        tuple(item.uv)
        for item in mesh.uv_layers["UVMap"].data
    ]


def make_object(label, with_materials=True):
    mesh = bpy.data.meshes.new(f"{prefix}_{label}")
    mesh.from_pydata(
        [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()

    layer = mesh.uv_layers.new(name="UVMap")
    for loop in mesh.loops:
        co = mesh.vertices[loop.vertex_index].co
        layer.data[loop.index].uv = (co.x, co.y)

    obj = bpy.data.objects.new(f"{prefix}_{label}", mesh)
    context.scene.collection.objects.link(obj)

    if with_materials:
        mesh.materials.append(material_a)
        mesh.materials.append(material_b)
        mesh.materials.append(material_a)
        obj.material_slots[2].material = None

        obj.material_slots[1].link = "OBJECT"
        obj.material_slots[1].material = material_c
        obj.active_material_index = 1

    context.view_layer.update()
    return obj


def preview(obj, test_context=None, style="PLAIN"):
    return checker_ops.apply_checker_preview(
        context if test_context is None else test_context,
        obj,
        uv_name="UVMap",
        width=1024,
        height=1024,
        style=style,
    )


def set_density(obj):
    return apply_uv_density(
        context,
        obj,
        uv_name="UVMap",
        width=1024,
        height=1024,
        target=512 / context.scene.unit_settings.scale_length,
    )


try:
    if context.mode != "OBJECT":
        raise RuntimeError("Run these tests in Object Mode")

    material_a = bpy.data.materials.new(f"{prefix}_MaterialA")
    material_b = bpy.data.materials.new(f"{prefix}_MaterialB")
    material_c = bpy.data.materials.new(f"{prefix}_MaterialC")

    obj = make_object("ExistingSlots")
    original_mesh = obj.data
    original_uvs = uv_coordinates(original_mesh)
    original_slots = [
        (slot.link, slot.material)
        for slot in obj.material_slots
    ]
    original_data_materials = list(original_mesh.materials)

    sibling = bpy.data.objects.new(
        f"{prefix}_SharedMesh",
        original_mesh,
    )
    context.scene.collection.objects.link(sibling)

    checker = preview(obj)
    checker_name = checker.name

    check(
        len(active_previews()) == 1
        and obj.data == original_mesh
        and all(
            slot.link == "OBJECT" and slot.material == checker
            for slot in obj.material_slots
        ),
        "Existing slots use object-linked checker overrides",
    )
    check(
        list(original_mesh.materials) == original_data_materials
        and sibling.material_slots[0].material == material_a
        and sibling.material_slots[1].material == material_b
        and sibling.material_slots[2].material is None,
        "Shared mesh materials and sibling assignments unchanged",
    )

    changed, _ = set_density(obj)
    edited_mesh = obj.data
    edited_uvs = uv_coordinates(edited_mesh)
    edited_mesh.vertices[0].co.z = 0.25

    restored, errors = checker_ops.restore_checker_previews(context)

    check(
        changed and restored == 1 and not errors and not active_previews()
        and [
            (slot.link, slot.material)
            for slot in obj.material_slots
        ] == original_slots
        and obj.active_material_index == 1,
        "Original links, empty slot, and active material restored",
    )
    check(
        obj.data == edited_mesh
        and uv_coordinates(obj.data) == edited_uvs
        and obj.data.vertices[0].co.z == 0.25
        and uv_coordinates(original_mesh) == original_uvs,
        "UV and geometry edits made during preview preserved",
    )
    check(
        bpy.data.materials.get(checker_name) is None,
        "Unused checker material removed",
    )

    obj = make_object("NoSlots", with_materials=False)
    original_mesh = obj.data
    sibling = bpy.data.objects.new(
        f"{prefix}_NoSlotsSibling",
        original_mesh,
    )
    context.scene.collection.objects.link(sibling)

    checker = preview(obj)
    checker_name = checker.name

    check(
        obj.data != original_mesh
        and len(obj.material_slots) == 1
        and len(original_mesh.materials) == 0,
        "Object without slots receives an independent checker mesh",
    )

    set_density(obj)
    edited_mesh = obj.data
    edited_uvs = uv_coordinates(edited_mesh)

    restored, errors = checker_ops.restore_checker_previews(context)

    check(
        restored == 1 and not errors
        and obj.data == edited_mesh
        and not obj.material_slots
        and uv_coordinates(obj.data) == edited_uvs
        and not sibling.material_slots,
        "Temporary slot removed while retaining UV edits",
    )
    check(
        bpy.data.materials.get(checker_name) is None,
        "Replacing a preview mesh does not retain its checker material",
    )

    obj = make_object("ChangedSlots")
    preview(obj)
    obj.data.materials.append(material_a)

    restored, errors = checker_ops.restore_checker_previews(context)
    check(
        restored == 0 and errors and len(active_previews()) == 1,
        "Unexpected slot count retains the restoration record",
    )

    obj.data.materials.pop(index=3)
    restored, errors = checker_ops.restore_checker_previews(context)
    check(
        restored == 1 and not errors and not active_previews(),
        "Restoration succeeds after correcting the slot count",
    )

    obj = make_object("AssignmentFailure")
    original_mesh = obj.data
    original_slots = [
        (slot.link, slot.material)
        for slot in obj.material_slots
    ]
    update_calls = 0

    def fail_second_update():
        global update_calls
        update_calls += 1
        if update_calls == 2:
            raise RuntimeError("Injected checker update failure")
        context.view_layer.update()

    test_context = SimpleNamespace(
        mode=context.mode,
        view_layer=SimpleNamespace(
            objects=context.view_layer.objects,
            update=fail_second_update,
        ),
    )

    caught = None
    before_materials = len(bpy.data.materials)

    try:
        preview(obj, test_context)
    except checker_ops.CheckerRecoveryError:
        raise
    except RuntimeError as error:
        caught = error

    check(
        caught is not None
        and "Injected" in str(caught)
        and obj.data == original_mesh
        and [
            (slot.link, slot.material)
            for slot in obj.material_slots
        ] == original_slots
        and not active_previews()
        and len(bpy.data.materials) == before_materials,
        "Assignment failure restores materials and cleans temporary data",
    )

    # Shift+D: the copy must inherit the checker and restore on its own.
    def shift_d(source, duplicate_mesh=True):
        copy = source.copy()
        if duplicate_mesh:
            copy.data = source.data.copy()
        context.scene.collection.objects.link(copy)
        context.view_layer.update()
        return copy

    obj = make_object("DupExisting")
    checker = preview(obj)
    checker_name = checker.name
    copy = shift_d(obj)

    check(
        copy.geprep_checker.active
        and copy.geprep_checker.checker == checker
        and len(copy.geprep_checker.slots) == 3,
        "Shift+D copy inherits the stored checker state",
    )

    restored, errors = checker_ops.restore_checker_previews(
        context, objects=[obj],
    )
    check(
        restored == 1 and not errors
        and bpy.data.materials.get(checker_name) is not None
        and copy.geprep_checker.active,
        "Restoring the source keeps the checker alive for the copy",
    )

    restored, errors = checker_ops.restore_checker_previews(
        context, objects=[copy],
    )
    check(
        restored == 1 and not errors
        and [
            (slot.link, slot.material)
            for slot in copy.material_slots
        ] == [
            (slot.link, slot.material)
            for slot in obj.material_slots
        ]
        and copy.active_material_index == 1
        and not active_previews()
        and bpy.data.materials.get(checker_name) is None,
        "Copy restored after the source; checker removed with last user",
    )

    obj = make_object("DupNoSlots", with_materials=False)
    preview(obj)
    copy = shift_d(obj)

    check(
        copy.geprep_checker.active
        and copy.geprep_checker.temporary_slot,
        "Shift+D copy of a temporary-slot preview is restorable",
    )

    restored, errors = checker_ops.restore_checker_previews(context)
    check(
        restored == 2 and not errors
        and not obj.material_slots
        and not copy.material_slots
        and not active_previews(),
        "Both temporary-slot objects restored; no slots left behind",
    )

    # Direction Checker: image-based material, cleaned up with the checker.
    obj = make_object("DirectionChecker")
    checker = preview(obj, style="DIRECTION")
    image_nodes = [
        node for node in checker.node_tree.nodes
        if node.type == "TEX_IMAGE"
    ]
    image = image_nodes[0].image if image_nodes else None
    image_name = image.name if image else None

    check(
        len(image_nodes) == 1
        and image is not None
        and image.size[0] == image.size[1] == 256
        and image.packed_file is not None,
        "Direction Checker uses a packed 256 px image tile",
    )

    restored, errors = checker_ops.restore_checker_previews(
        context, objects=[obj],
    )
    check(
        restored == 1 and not errors
        and bpy.data.images.get(image_name) is None
        and not active_previews(),
        "Removing the Direction Checker also removes its image",
    )

    obj = make_object("BadStyle")
    try:
        preview(obj, style="NOPE")
        raise AssertionError("An unknown checker style must be rejected")
    except ValueError:
        pass

    check(
        not obj.geprep_checker.active and not active_previews(),
        "Unknown checker style leaves no checker state behind",
    )

    print("ALL CHECKER WORKFLOW TESTS PASSED")

finally:
    checker_ops.create_checker_material = original_create
    for obj in bpy.data.objects:
        if obj.name.startswith(prefix):
            checker_ops.clear_checker_state(obj)

    for obj in list(bpy.data.objects):
        if obj.name.startswith(prefix):
            bpy.data.objects.remove(obj, do_unlink=True)

    for mesh in list(bpy.data.meshes):
        if mesh.name.startswith(prefix) and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

    bpy.data.scenes.remove(test_scene)

    for material in list(bpy.data.materials):
        if (
            material.name.startswith(prefix)
            or material.name in checker_names
        ) and material.users == 0:
            bpy.data.materials.remove(material)

    context.view_layer.update()
    print("Temporary test scene, objects, meshes, and materials removed")
""")

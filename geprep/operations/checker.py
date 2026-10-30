import bpy

from .direction_checker_pixels import (
    TILE_CELLS,
    TILE_PIXELS,
    build_direction_checker_pixels,
)
from .uv import read_uv_map

# (style, button label, tooltip)
CHECKER_STYLES = (
    (
        "PLAIN",
        "Checker",
        "Show a 64-pixel UV checker on the selected objects",
    ),
    (
        "DIRECTION",
        "Direction Checker",
        "Show a UV checker with a cyan +U arrow and an orange +V arrow "
        "in every square. Shows rotation and mirroring",
    ),
)

# One checker square is 64 texture pixels wide.
CHECKER_SQUARE_PIXELS = 64


def remove_checker_material(material):
    """Remove a checker material and any image only it was using."""
    images = set()

    if material.node_tree is not None:
        images = {
            node.image
            for node in material.node_tree.nodes
            if node.type == "TEX_IMAGE" and node.image is not None
        }

    bpy.data.materials.remove(material)

    for image in images:
        if image.users == 0:
            bpy.data.images.remove(image)


def create_direction_image():
    """Create the packed tile used by the Direction Checker."""
    image = bpy.data.images.new(
        "GEPrep Direction Checker",
        TILE_PIXELS,
        TILE_PIXELS,
        alpha=False,
    )

    try:
        pixels = build_direction_checker_pixels()
        image.pixels.foreach_set(pixels.ravel())
        image.pack()

        return image

    except Exception:
        bpy.data.images.remove(image)
        raise


def create_checker_material(uv_name, width, height, style="PLAIN"):
    """Create an unassigned UV checker material with 64-pixel squares."""
    if style not in {key for key, _, _ in CHECKER_STYLES}:
        raise ValueError(f"Unknown checker style: {style}")

    if not uv_name:
        raise ValueError("A UV map name is required")

    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or width <= 0
        or height <= 0
    ):
        raise ValueError("Texture dimensions must be positive integers")

    material = bpy.data.materials.new(name="GEPrep UV Checker")

    try:
        material.diffuse_color = (0.8, 0.8, 0.8, 1.0)

        nodes = material.node_tree.nodes
        links = material.node_tree.links
        nodes.clear()

        uv = nodes.new("ShaderNodeUVMap")
        uv.uv_map = uv_name
        uv.location = (-600, 0)

        scale = nodes.new("ShaderNodeVectorMath")
        scale.operation = "MULTIPLY"
        # The plain checker repeats every square. The direction image
        # repeats every two squares.
        repeat_pixels = (
            CHECKER_SQUARE_PIXELS
            if style == "PLAIN"
            else CHECKER_SQUARE_PIXELS * TILE_CELLS
        )
        scale.inputs[1].default_value = (
            width / repeat_pixels,
            height / repeat_pixels,
            1.0,
        )
        scale.location = (-400, 0)

        if style == "PLAIN":
            checker = nodes.new("ShaderNodeTexChecker")
            checker.inputs["Scale"].default_value = 1.0
            checker.inputs["Color1"].default_value = (
                0.02, 0.02, 0.02, 1.0,
            )
            checker.inputs["Color2"].default_value = (
                0.8, 0.8, 0.8, 1.0,
            )

        else:
            checker = nodes.new("ShaderNodeTexImage")
            checker.image = create_direction_image()
            checker.interpolation = "Linear"
            checker.extension = "REPEAT"

        checker.location = (-200, 0)

        shader = nodes.new("ShaderNodeBsdfPrincipled")
        shader.inputs["Roughness"].default_value = 0.8
        shader.location = (50, 0)

        output = nodes.new("ShaderNodeOutputMaterial")
        output.location = (350, 0)

        links.new(uv.outputs["UV"], scale.inputs[0])
        links.new(scale.outputs["Vector"], checker.inputs["Vector"])
        links.new(checker.outputs["Color"], shader.inputs["Base Color"])
        links.new(shader.outputs["BSDF"], output.inputs["Surface"])

        return material

    except Exception as error:
        error.add_note("GEPrep: failed to create the UV checker material")
        remove_checker_material(material)
        raise


def has_checker_preview(obj):
    """Return whether this object carries a stored checker preview."""
    return obj is not None and obj.geprep_checker.active


def clear_checker_state(obj):
    """Forget the stored checker state of one object."""
    state = obj.geprep_checker
    state.active = False
    state.slots.clear()
    state.checker = None
    state.temporary_slot = False
    state.active_material_index = 0


def restore_checker_materials(obj):
    """Restore one object's materials without replacing its mesh."""
    record = obj.geprep_checker
    checker = record.checker

    if obj.type != "MESH":
        raise ValueError("The object is no longer a mesh")

    if not obj.is_editable or obj.override_library is not None:
        raise ValueError("Use an editable local object")

    if record.temporary_slot:
        if not obj.data.is_editable:
            raise ValueError("The mesh data cannot be edited")

        if len(obj.material_slots) > 1:
            raise ValueError(
                "Additional material slots were added. "
                "Remove those slots before removing the checker"
            )

        if any(
            material is not None and material != checker
            for material in obj.data.materials
        ):
            raise ValueError(
                "The temporary mesh slot contains another material. "
                "Clear that assignment before removing the checker"
            )

        if any(
            slot.material is not None and slot.material != checker
            for slot in obj.material_slots
        ):
            raise ValueError(
                "The temporary object slot contains another material. "
                "Clear that assignment before removing the checker"
            )

        for slot in obj.material_slots:
            slot.link = "OBJECT"
            slot.material = None

        obj.data.materials.clear()

        if obj.material_slots:
            raise RuntimeError("Could not remove the temporary material slot")

        obj.active_material_index = 0
        return

    if len(obj.material_slots) != len(record.slots):
        raise ValueError(
            f"Material slot count changed from {len(record.slots)} "
            f"to {len(obj.material_slots)}. "
            "Restore the original slot count before removing the checker"
        )

    # Check data-linked assignments before changing any object overrides.
    for index, original in enumerate(record.slots):
        if (
            original.link == "DATA"
            and obj.data.materials[index] != original.material
        ):
            raise ValueError(
                f"Mesh material in slot {index + 1} changed. "
                "Restore its original assignment before removing the checker"
            )

    for slot, original in zip(obj.material_slots, record.slots):
        # Release the checker from the object override, including when
        # the restored slot will use its mesh-linked material.
        slot.link = "OBJECT"
        slot.material = None
        slot.link = original.link

        if original.link == "OBJECT":
            slot.material = original.material

    obj.active_material_index = record.active_material_index


def restore_checker_previews(context, *, objects=None):
    """Restore chosen objects; keep the state of objects that fail.

    The checker state is stored on each object, so a duplicate made with
    Shift+D carries it along and can be restored on its own.
    """
    if objects is None:
        candidates = list(context.scene.objects)
    else:
        candidates = list(objects)

    restored = 0
    errors = []
    materials = set()

    for obj in sorted(
        (obj for obj in candidates if has_checker_preview(obj)),
        key=lambda obj: (obj.name.casefold(), obj.name),
    ):
        checker = obj.geprep_checker.checker

        try:
            restore_checker_materials(obj)
            context.view_layer.update()
            clear_checker_state(obj)
            restored += 1

            if checker is not None:
                materials.add(checker)

        except Exception as error:
            errors.append(f"{obj.name}: {error}")

    for material in materials:
        try:
            if material.users == 0:
                remove_checker_material(material)

        except Exception as error:
            errors.append(
                f"Could not remove unused checker material: {error}"
            )

    return restored, errors


class CheckerRecoveryError(RuntimeError):
    """Checker assignment failed and recovery was incomplete."""


def apply_checker_preview(
    context,
    obj,
    *,
    uv_name="",
    width=2048,
    height=2048,
    style="PLAIN",
):
    """Show a checker while recording the original material assignments."""
    if context.mode != "OBJECT":
        raise ValueError("Return to Object Mode before showing the checker")

    if obj.type != "MESH":
        raise ValueError("Select a mesh object")

    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError("This object is not in the current view layer")

    if (
        not obj.is_editable
        or obj.library is not None
        or obj.override_library is not None
    ):
        raise ValueError("Use an editable local object")

    if has_checker_preview(obj):
        raise ValueError("This object already has a checker preview")

    name, _ = read_uv_map(obj.data, uv_name)

    if not obj.data.polygons:
        raise ValueError("This mesh has no faces to preview")

    temporary_slot = not obj.material_slots

    if temporary_slot and obj.is_property_readonly("data"):
        raise ValueError(
            "This object cannot use an independent mesh for the checker"
        )

    context.view_layer.update()

    if any(modifier.show_viewport for modifier in obj.modifiers):
        evaluated = obj.evaluated_get(
            context.evaluated_depsgraph_get()
        )

        if [
            slot.material
            for slot in evaluated.material_slots
        ] != [
            slot.material
            for slot in obj.material_slots
        ]:
            raise ValueError(
                "Enabled modifiers change the material slots. "
                "Apply them before showing the checker"
            )

    original_mesh = obj.data
    original_active = obj.active_material_index
    original_slots = [
        (slot.link, slot.material)
        for slot in obj.material_slots
    ]

    checker = None
    working_mesh = None
    record = obj.geprep_checker
    record_started = False
    assignment_started = False
    stage = "create checker material"

    try:
        checker = create_checker_material(name, width, height, style)

        stage = "record original materials"
        record_started = True
        record.active = True
        record.checker = checker
        record.temporary_slot = temporary_slot
        record.active_material_index = original_active

        for link, material in original_slots:
            saved = record.slots.add()
            saved.link = link
            saved.material = material

        if temporary_slot:
            stage = "copy mesh for temporary material slot"
            working_mesh = original_mesh.copy()
            working_mesh.use_fake_user = False

            stage = "assign checker mesh"
            assignment_started = True
            obj.data = working_mesh
            working_mesh.materials.append(checker)

            slot = obj.material_slots[0]
            slot.material = None
            slot.link = "OBJECT"
            slot.material = checker

        else:
            stage = "assign checker material overrides"
            assignment_started = True

            for slot in obj.material_slots:
                slot.link = "OBJECT"
                slot.material = checker

        stage = "update checker preview"
        context.view_layer.update()

        return checker

    except Exception as error:
        error.add_note(
            f"GEPrep: failed to {stage} on object {obj.name!r}"
        )

        recovery_stage = "restore original materials"

        try:
            if assignment_started:
                if temporary_slot:
                    obj.data = original_mesh
                    obj.active_material_index = original_active
                else:
                    restore_checker_materials(obj)

                context.view_layer.update()

            recovery_stage = "remove unused checker mesh"

            if working_mesh is not None and working_mesh.users == 0:
                bpy.data.meshes.remove(working_mesh)

            recovery_stage = "remove restoration record"

            if record_started:
                clear_checker_state(obj)

            recovery_stage = "remove unused checker material"

            if checker is not None and checker.users == 0:
                remove_checker_material(checker)

        except Exception as recovery_error:
            raise CheckerRecoveryError(
                f"Failed to {stage}: {error}. "
                f"Could not {recovery_stage}: {recovery_error}. "
                "Use Undo"
            ) from recovery_error

        raise

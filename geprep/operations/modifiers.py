import bpy

from ..helpers.objects import has_animation, restore_material_links


def nodes_have_simulation(node_tree, visited=None):
    """Check a node tree and nested groups for simulation zones."""
    if node_tree is None:
        return False

    if visited is None:
        visited = set()

    if node_tree in visited:
        return False

    visited.add(node_tree)

    for node in node_tree.nodes:
        if node.bl_idname == "GeometryNodeSimulationOutput":
            return True

        nested_tree = getattr(node, "node_tree", None)

        if nodes_have_simulation(nested_tree, visited):
            return True

    return False


def validate_modifier_apply(obj):
    """Validate the object and return enabled modifier names in stack order."""
    if obj.type != "MESH":
        raise ValueError("Select a mesh object")

    modifier_names = [
        modifier.name
        for modifier in obj.modifiers
        if modifier.show_viewport
    ]

    if not modifier_names:
        return []

    if not obj.is_editable or obj.library is not None:
        raise ValueError("This object cannot be edited. Use a local copy")

    if obj.override_library is not None:
        raise ValueError("This object is a library override. Use a local copy")

    if obj.data.shape_keys is not None:
        raise ValueError(
            "This mesh has shape keys. Use a mesh without shape keys"
        )

    if has_animation(obj) or has_animation(obj.data):
        raise ValueError(
            "This object or its mesh has animation. "
            "Use an unanimated copy before applying modifiers"
        )

    simulation_types = {
        "CLOTH",
        "SOFT_BODY",
        "FLUID",
        "DYNAMIC_PAINT",
        "PARTICLE_SYSTEM",
    }

    for name in modifier_names:
        modifier = obj.modifiers[name]

        if modifier.type in simulation_types:
            raise ValueError(
                f"Modifier {name!r} uses a simulation. "
                "Bake it separately before applying modifiers"
            )

        if (
            modifier.type == "NODES"
            and nodes_have_simulation(modifier.node_group)
        ):
            raise ValueError(
                f"Modifier {name!r} contains a simulation zone. "
                "Bake it separately before applying modifiers"
            )

    return modifier_names


class ModifierRecoveryError(RuntimeError):
    """Applying modifiers failed and recovery was incomplete."""


def restore_modifier_stack(context, obj, backup):
    """Restore modifiers from the saved object."""
    if not backup.users_collection:
        context.scene.collection.objects.link(backup)

    backup.hide_viewport = False
    backup.hide_select = False
    backup.hide_set(False, view_layer=context.view_layer)
    context.view_layer.update()

    for modifier in tuple(obj.modifiers):
        obj.modifiers.remove(modifier)

    # Blender copies modifiers from the active object to selected objects.
    with context.temp_override(
        object=backup,
        active_object=backup,
        selected_objects=[backup, obj],
        selected_editable_objects=[backup, obj],
    ):
        for modifier in backup.modifiers:
            result = bpy.ops.object.modifier_copy_to_selected(
                modifier=modifier.name,
            )

            if "FINISHED" not in result:
                raise RuntimeError(
                    f"Could not restore modifier {modifier.name!r}"
                )

    expected = [
        (modifier.name, modifier.type)
        for modifier in backup.modifiers
    ]
    restored = [
        (modifier.name, modifier.type)
        for modifier in obj.modifiers
    ]

    if restored != expected:
        raise RuntimeError(
            "The restored modifier stack does not match the backup"
        )


def restore_modifier_vertex_groups(obj, groups, active_index):
    """Restore group definitions; the original mesh supplies their weights."""
    expected_names = [name for name, _ in groups]
    current_names = [group.name for group in obj.vertex_groups]

    if current_names != expected_names:
        for group in tuple(obj.vertex_groups):
            obj.vertex_groups.remove(group)

        for name, locked in groups:
            group = obj.vertex_groups.new(name=name)
            group.lock_weight = locked
    else:
        for group, (_, locked) in zip(obj.vertex_groups, groups):
            group.lock_weight = locked

    if groups:
        obj.vertex_groups.active_index = active_index


def apply_object_modifiers(context, obj):
    """Apply viewport-enabled modifiers and restore the object on failure."""
    if context.mode != "OBJECT":
        raise ValueError("Switch to Object Mode first")

    if context.view_layer.objects.get(obj.name) != obj:
        raise ValueError("This object is not in the current view layer")

    if obj.geprep_checker.active:
        raise ValueError("Remove the checker before applying modifiers")

    modifier_names = validate_modifier_apply(obj)

    if not modifier_names:
        return 0

    original_mesh = obj.data
    original_slots = [
        (slot.link, slot.material)
        for slot in obj.material_slots
    ]
    original_material_index = obj.active_material_index
    original_groups = [
        (group.name, group.lock_weight)
        for group in obj.vertex_groups
    ]
    original_group_index = obj.vertex_groups.active_index

    backup = None
    temporary_meshes = set()
    changed = False
    keep_backup = False
    stage = "create object backup"

    try:
        backup = obj.copy()

        stage = "copy mesh data"
        working_mesh = original_mesh.copy()
        temporary_meshes.add(working_mesh)
        working_mesh.use_fake_user = False

        stage = "assign working mesh"
        obj.data = working_mesh
        changed = True

        stage = "update working mesh"
        context.view_layer.update()

        with context.temp_override(
            object=obj,
            active_object=obj,
            selected_objects=[obj],
            selected_editable_objects=[obj],
        ):
            for name in modifier_names:
                stage = f"apply modifier {name!r}"

                if obj.modifiers.get(name) is None:
                    raise RuntimeError(
                        "The modifier disappeared before it could be applied"
                    )

                result = bpy.ops.object.modifier_apply(modifier=name)

                if "FINISHED" not in result:
                    raise RuntimeError(
                        "Blender did not finish applying the modifier"
                    )

                if obj.modifiers.get(name) is not None:
                    raise RuntimeError(
                        "The modifier is still present after applying it"
                    )

                context.view_layer.update()

        return len(modifier_names)

    except Exception as error:
        error.add_note(
            f"GEPrep: failed to {stage} on object {obj.name!r}"
        )

        if changed:
            recovery_stage = "prepare mesh for recovery"

            try:
                output_mesh = obj.data

                if output_mesh != original_mesh:
                    temporary_meshes.add(output_mesh)

                # Group removal must never modify the original or shared mesh.
                if output_mesh == original_mesh or output_mesh.users > 1:
                    recovery_mesh = output_mesh.copy()
                    temporary_meshes.add(recovery_mesh)
                    recovery_mesh.use_fake_user = False
                    obj.data = recovery_mesh

                recovery_stage = "restore vertex groups"
                restore_modifier_vertex_groups(
                    obj,
                    original_groups,
                    original_group_index,
                )

                recovery_stage = "restore original mesh"
                obj.data = original_mesh

                recovery_stage = "restore material assignments"
                restore_material_links(
                    obj,
                    original_slots,
                    original_material_index,
                )

                recovery_stage = "restore modifier stack"
                restore_modifier_stack(context, obj, backup)

                recovery_stage = "update restored object"
                context.view_layer.update()

            except Exception as recovery_error:
                keep_backup = True
                backup.use_fake_user = True

                raise ModifierRecoveryError(
                    f"Failed to {stage}: {error}. "
                    f"Could not {recovery_stage}: {recovery_error}. "
                    f"Use Undo. Backup kept as {backup.name!r}"
                ) from recovery_error

        raise

    finally:
        cleanup_errors = []

        if backup is not None and not keep_backup:
            try:
                bpy.data.objects.remove(backup, do_unlink=True)
            except Exception as cleanup_error:
                cleanup_errors.append(
                    f"Could not remove object backup: {cleanup_error}"
                )

        for mesh in temporary_meshes:
            try:
                if mesh != original_mesh and mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            except Exception as cleanup_error:
                cleanup_errors.append(
                    f"Could not remove temporary mesh: {cleanup_error}"
                )

        if cleanup_errors:
            raise ModifierRecoveryError(
                "Modifier cleanup was incomplete. "
                + "; ".join(cleanup_errors)
                + ". Use Undo"
            )

import bpy
from math import isclose
from ..helpers.objects import has_animation
from .naming import remove_numeric_suffix, reserve_name


def collect_prepare_sources(selected, include_children):
    """Collect selected meshes and optionally their hierarchy, once each."""
    roots = [
        obj
        for obj in selected
        if obj.type == "MESH"
        or (include_children and obj.type == "EMPTY")
    ]

    found = set()
    pending = list(roots)

    while pending:
        obj = pending.pop()

        if obj in found:
            continue

        if obj.type not in {"MESH", "EMPTY"}:
            raise ValueError(
                f"Cannot prepare {obj.name!r}: "
                f"unsupported object type {obj.type!r}. "
                "Disable Include Children to prepare only selected meshes"
            )

        found.add(obj)

        if include_children:
            pending.extend(obj.children)

    if not any(obj.type == "MESH" for obj in found):
        return []

    return sorted(
        found,
        key=lambda obj: (obj.name.casefold(), obj.name),
    )


def validate_prepare_sources(context, sources, *, apply_rotation_scale=False):
    """Reject unsupported sources before creating prepared copies."""
    problems = []

    for obj in sources:
        if obj.geprep_checker.active:
            problems.append(
                "Remove the checker before creating prepared copies"
            )

        if obj.library is not None:
            problems.append(f"{obj.name!r} is linked. Make it local first")
        elif obj.override_library is not None:
            problems.append(f"{obj.name!r} is a library override. Use a local copy")
        elif not obj.is_editable:
            problems.append(f"{obj.name!r} cannot be edited")

        if obj.name not in context.view_layer.objects:
            problems.append(
                f"{obj.name!r} is outside the current view layer"
            )

        if obj.parent is not None and obj.parent_type != "OBJECT":
            problems.append(
                f"{obj.name!r} uses {obj.parent_type!r} parenting. "
                "Only object parenting is supported"
            )

        if apply_rotation_scale:
            if obj.constraints:
                problems.append(
                    f"{obj.name!r} has constraints. "
                    "Disable Apply Rotation & Scale"
                )

            if has_animation(obj):
                problems.append(
                    f"{obj.name!r} has object animation or drivers. "
                    "Disable Apply Rotation & Scale"
                )

    if problems:
        raise ValueError(
            "Cannot prepare these objects:\n" + "\n".join(problems)
        )


def plan_prepare_names(
    sources,
    existing_names,
    *,
    use_sm_prefix=True,
    number_variants=False,
):
    """Reserve names for prepared copies without creating any objects."""
    reserved = set(existing_names)
    reserved.update(obj.name for obj in sources)
    planned_names = {}

    ordered_sources = sorted(
        sources,
        key=lambda obj: (obj.name.casefold(), obj.name),
    )

    for obj in ordered_sources:
        if obj.type == "MESH":
            stem = remove_numeric_suffix(obj.name)

            if use_sm_prefix and not stem.startswith("SM_"):
                stem = f"SM_{stem}"

            requested = f"{stem}.001" if number_variants else stem

        elif obj.type == "EMPTY":
            requested = f"{obj.name}_Prepared"

        else:
            raise ValueError(
                f"Cannot plan a prepared name for {obj.name!r}: "
                f"unsupported object type {obj.type!r}"
            )

        planned_names[obj] = reserve_name(requested, reserved)

    return planned_names


def create_prepare_copies(
    sources,
    planned_names,
    *,
    duplicate_materials=False,
):
    """Create prepared copies without changing or hiding the originals."""
    sources = list(sources)
    copies = {}
    meshes = []
    materials = {}

    world_matrices = {
        source: source.matrix_world.copy()
        for source in sources
    }

    try:
        for source in sources:
            duplicate = source.copy()
            copies[source] = duplicate

            if source.type == "MESH":
                duplicate.data = source.data.copy()
                duplicate.data.use_fake_user = False
                meshes.append(duplicate.data)

                if duplicate_materials:
                    for slot in duplicate.material_slots:
                        material = slot.material

                        if material is None:
                            continue

                        if material not in materials:
                            materials[material] = material.copy()

                        slot.material = materials[material]

            requested_name = planned_names[source]
            duplicate.name = requested_name

            if duplicate.name != requested_name:
                raise RuntimeError(
                    f"Requested copy name {requested_name!r}, "
                    f"but Blender assigned {duplicate.name!r}"
                )

            for collection in source.users_collection:
                collection.objects.link(duplicate)

            duplicate.hide_viewport = False
            duplicate.hide_render = False
            duplicate.hide_select = False
            duplicate.hide_set(False)

        # Use copied parents where available; retain external parents.
        for source, duplicate in copies.items():
            duplicate.parent = copies.get(source.parent, source.parent)
            duplicate.matrix_parent_inverse = source.matrix_parent_inverse.copy()
            duplicate.matrix_world = world_matrices[source]

    except Exception as error:
        error.add_note("GEPrep: failed to create prepared copies")

        try:
            remove_prepare_copies(
                copies,
                extra_meshes=meshes,
                extra_materials=materials.values(),
            )
        except PrepareRecoveryError as recovery_error:
            raise PrepareRecoveryError(
                f"{recovery_error}\n"
                f"Original preparation error: {error}"
            ) from error

        raise

    return copies


def parent_depth(obj):
    """Count an object's ancestors."""
    depth = 0

    while obj.parent is not None:
        depth += 1
        obj = obj.parent

    return depth


def matrices_match(first, second, tolerance=0.00001):
    """Compare transforms, allowing small floating-point differences."""
    return all(
        isclose(
            first[row][column],
            second[row][column],
            rel_tol=tolerance,
            abs_tol=tolerance,
        )
        for row in range(4)
        for column in range(4)
    )


def apply_prepare_transforms(context, copies):
    """Apply mesh-copy rotation and scale without moving their geometry."""
    if not copies:
        return

    validate_prepare_sources(
        context,
        copies.keys(),
        apply_rotation_scale=True,
    )

    context.view_layer.update()

    # Temporarily use original parents. Applying a copied parent's transforms
    # must not affect another prepared copy while its transforms are applied.
    world_matrices = {
        source: duplicate.matrix_world.copy()
        for source, duplicate in copies.items()
    }

    for source, duplicate in copies.items():
        duplicate.parent = source.parent
        duplicate.matrix_parent_inverse = source.matrix_parent_inverse.copy()
        duplicate.matrix_world = world_matrices[source]

    context.view_layer.update()

    meshes = [
        duplicate
        for source, duplicate in copies.items()
        if source.type == "MESH"
    ]

    if meshes:
        try:
            with context.temp_override(
                object=meshes[0],
                active_object=meshes[0],
                selected_objects=meshes,
                selected_editable_objects=meshes,
            ):
                result = bpy.ops.object.transform_apply(
                    location=False,
                    rotation=True,
                    scale=True,
                    properties=False,
                )

            if "FINISHED" not in result:
                raise RuntimeError(
                    "Blender did not finish applying Rotation & Scale"
                )

        except Exception as error:
            error.add_note(
                "GEPrep: failed to apply Rotation & Scale to prepared meshes"
            )
            raise

    context.view_layer.update()

    # Reconnect copied parents without changing the applied local transforms.
    for source in sorted(copies, key=parent_depth):
        copied_parent = copies.get(source.parent)

        if copied_parent is None:
            continue

        duplicate = copies[source]
        before = duplicate.matrix_world.copy()

        try:
            parent_inverse = (
                copied_parent.matrix_world.inverted()
                @ source.parent.matrix_world
                @ duplicate.matrix_parent_inverse
            )

            duplicate.parent = copied_parent
            duplicate.matrix_parent_inverse = parent_inverse

            context.view_layer.update()

            if not matrices_match(before, duplicate.matrix_world):
                raise RuntimeError(
                    "The copy's world transform changed after reconnecting its parent"
                )

        except Exception as error:
            error.add_note(
                f"GEPrep: failed to reconnect the prepared parent of {source.name!r}"
            )
            raise


class PrepareRecoveryError(RuntimeError):
    """Preparation failed and cleanup could not finish."""


def remove_prepare_copies(
    copies,
    *,
    extra_meshes=(),
    extra_materials=(),
):
    """Remove copies and their unused mesh/material data."""
    duplicates = list(copies.values())

    meshes = set(extra_meshes)
    materials = set(extra_materials)

    for duplicate in duplicates:
        if duplicate.type == "MESH":
            meshes.add(duplicate.data)

            for slot in duplicate.material_slots:
                if slot.material is not None:
                    materials.add(slot.material)

    errors = []

    for duplicate in reversed(duplicates):
        name = duplicate.name

        try:
            bpy.data.objects.remove(duplicate, do_unlink=True)
        except Exception as error:
            errors.append(f"Could not remove object {name!r}: {error}")

    for mesh in meshes:
        name = mesh.name

        try:
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        except Exception as error:
            errors.append(f"Could not remove mesh {name!r}: {error}")

    for material in materials:
        name = material.name

        try:
            if material.users == 0:
                bpy.data.materials.remove(material)
        except Exception as error:
            errors.append(f"Could not remove material {name!r}: {error}")

    if errors:
        raise PrepareRecoveryError(
            "Could not completely clean up prepared copies:\n"
            + "\n".join(errors)
            + "\nUse Undo before continuing"
        )


def prepare_assets(
    context,
    *,
    include_children=True,
    use_sm_prefix=True,
    number_variants=False,
    duplicate_materials=False,
    apply_rotation_scale=False,
):
    """Prepare a copied batch, restoring original state on failure."""
    if context.mode != "OBJECT":
        raise ValueError("Prepare requires Object Mode")

    if not context.scene.is_editable:
        raise ValueError("The current scene cannot be edited")

    original_selection = tuple(context.selected_objects)
    original_active = context.view_layer.objects.active

    sources = collect_prepare_sources(
        original_selection,
        include_children,
    )

    if not sources:
        raise ValueError("Select at least one mesh or a hierarchy containing meshes")

    validate_prepare_sources(
        context,
        sources,
        apply_rotation_scale=apply_rotation_scale,
    )

    planned_names = plan_prepare_names(
        sources,
        (obj.name for obj in bpy.data.objects),
        use_sm_prefix=use_sm_prefix,
        number_variants=number_variants,
    )

    original_visibility = {
        source: (
            source.hide_viewport,
            source.hide_render,
            source.hide_select,
            source.hide_get(view_layer=context.view_layer),
        )
        for source in sources
    }

    copies = {}
    stage = "create copies"

    try:
        copies = create_prepare_copies(
            sources,
            planned_names,
            duplicate_materials=duplicate_materials,
        )

        if apply_rotation_scale:
            stage = "apply Rotation & Scale"
            apply_prepare_transforms(context, copies)

        # Hide originals only after copying and transform application succeed.
        stage = "hide originals"

        for source in sources:
            source.hide_viewport = True
            source.hide_render = True

        context.view_layer.update()

        stage = "select prepared copies"

        for obj in tuple(context.selected_objects):
            obj.select_set(False, view_layer=context.view_layer)

        for duplicate in copies.values():
            duplicate.select_set(True, view_layer=context.view_layer)

        context.view_layer.objects.active = copies.get(
            original_active,
            next(iter(copies.values())),
        )

    except Exception as error:
        error.add_note(f"GEPrep: failed to {stage}")
        recovery_errors = []

        # Creation may already have reported an incomplete cleanup.
        if isinstance(error, PrepareRecoveryError):
            recovery_errors.append(str(error))

        if copies:
            try:
                remove_prepare_copies(copies)
            except Exception as recovery_error:
                recovery_errors.append(str(recovery_error))

        # Attempt every restoration even if another restoration fails.
        for source, values in original_visibility.items():
            try:
                source.hide_viewport = values[0]
                source.hide_render = values[1]
                source.hide_select = values[2]
                source.hide_set(
                    values[3],
                    view_layer=context.view_layer,
                )
            except Exception as recovery_error:
                recovery_errors.append(
                    f"Could not restore visibility of "
                    f"{source.name!r}: {recovery_error}"
                )

        try:
            context.view_layer.update()

            for obj in tuple(context.selected_objects):
                obj.select_set(False, view_layer=context.view_layer)

            for obj in original_selection:
                obj.select_set(True, view_layer=context.view_layer)

            context.view_layer.objects.active = original_active

        except Exception as recovery_error:
            recovery_errors.append(
                f"Could not restore selection: {recovery_error}"
            )

        if recovery_errors:
            raise PrepareRecoveryError(
                f"Preparation failed during {stage}: {error}\n"
                + "\n".join(recovery_errors)
                + "\nUse Undo before continuing"
            ) from error

        raise

    return {
        "copies": copies,
        "original_visibility": original_visibility,
        "original_selection": original_selection,
        "original_active": original_active,
        "view_layer": context.view_layer.name,
    }


def find_selected_prepare_batches(context, batches):
    """Find batches containing selected prepared copies."""
    selected = set(context.selected_objects)

    return [
        index
        for index, batch in enumerate(batches)
        if any(
            entry.duplicate is not None
            and entry.duplicate in selected
            for entry in batch.entries
        )
    ]


def remove_prepare_batch(context, batches, index):
    """Remove selected copies from a batch and restore their originals."""
    if context.mode != "OBJECT":
        raise ValueError("Removing prepared copies requires Object Mode")

    if not 0 <= index < len(batches):
        raise ValueError("The prepared batch no longer exists")

    batch = batches[index]

    if context.view_layer.name != batch.view_layer:
        raise ValueError(
            f"Switch to view layer {batch.view_layer!r} "
            "before removing this batch"
        )

    selected = set(context.selected_objects)

    entry_indices = [
        entry_index
        for entry_index, entry in enumerate(batch.entries)
        if entry.duplicate is not None
        and entry.duplicate in selected
    ]

    entries = [
        batch.entries[entry_index]
        for entry_index in entry_indices
    ]

    if not entries:
        raise ValueError("Select prepared copies to remove")

    copies = {}
    sources = set()

    # Validate everything before changing visibility or deleting objects.
    for number, entry in enumerate(entries, start=1):
        source = entry.source
        duplicate = entry.duplicate

        if source is None:
            raise ValueError(
                f"Original object for batch entry {number} no longer exists"
            )

        if not source.is_editable:
            raise ValueError(
                f"Original object {source.name!r} cannot be edited"
            )

        if source.name not in context.view_layer.objects:
            raise ValueError(
                f"Original object {source.name!r} is outside this view layer"
            )

        if source in sources:
            raise ValueError("The batch contains duplicate original-object records")

        sources.add(source)

        if duplicate is not None:
            if not duplicate.is_editable:
                raise ValueError(
                    f"Prepared copy {duplicate.name!r} cannot be removed"
                )

            copies[source] = duplicate

    if sources.intersection(copies.values()):
        raise ValueError(
            "The batch incorrectly identifies an original as a prepared copy"
        )

    # Removing an older batch must not invalidate another batch.
    duplicates = set(copies.values())

    for other_index, other_batch in enumerate(batches):
        if other_index == index:
            continue

        if any(
            entry.source is not None
            and (
                entry.source in duplicates
                or entry.source in sources
            )
            for entry in other_batch.entries
        ):
            raise ValueError(
                "Another prepared batch depends on this batch or shares "
                "its originals. Remove that batch first"
            )

    # Keep objects outside this batch from losing their prepared parent.
    if any(
        child not in duplicates
        for duplicate in duplicates
        for child in duplicate.children
    ):
        raise ValueError(
            "A prepared copy has children outside this batch. "
            "Reparent those children before removing the batch"
        )

    if any(duplicate.geprep_checker.active for duplicate in duplicates):
        raise ValueError(
            "Remove the checker from the prepared copies "
            "before removing this batch"
        )

    # Keep unrelated selected objects and select the restored originals.
    original_selection = [
        obj
        for obj in context.selected_objects
        if obj not in duplicates
    ]

    for entry in entries:
        if entry.source not in original_selection:
            original_selection.append(entry.source)

    original_active = context.view_layer.objects.active

    # Replace an active prepared copy with its corresponding original.
    for entry in entries:
        if entry.duplicate == original_active:
            original_active = entry.source
            break
    removed_count = len(copies)
    stage = "restore original visibility"

    try:
        for entry in entries:
            source = entry.source
            source.hide_viewport = entry.original_hide_viewport
            source.hide_render = entry.original_hide_render
            source.hide_select = entry.original_hide_select
            source.hide_set(
                entry.original_hidden,
                view_layer=context.view_layer,
            )

        context.view_layer.update()

        stage = "remove prepared copies"
        remove_prepare_copies(copies)

        stage = "restore original selection"

        for obj in tuple(context.selected_objects):
            obj.select_set(False, view_layer=context.view_layer)

        for obj in original_selection:
            if (
                not obj.hide_select
                and obj.visible_get(view_layer=context.view_layer)
            ):
                obj.select_set(True, view_layer=context.view_layer)

        selected_after = list(context.selected_objects)

        if original_active is not None and original_active in selected_after:
            context.view_layer.objects.active = original_active
        else:
            context.view_layer.objects.active = (
                selected_after[0] if selected_after else None
            )

        stage = "remove the completed restoration records"

        for entry_index in reversed(entry_indices):
            batch.entries.remove(entry_index)

        # Keep restoration records for copies that were not removed.
        if not batch.entries:
            batches.remove(index)

    except Exception as error:
        raise PrepareRecoveryError(
            f"Could not finish removing the prepared batch during "
            f"{stage}: {error}. Use Undo before continuing"
        ) from error

    return removed_count




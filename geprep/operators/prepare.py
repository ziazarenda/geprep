import traceback

import bpy

from ..operations.prepare import (
    PrepareRecoveryError,
    find_selected_prepare_batches,
    prepare_assets,
    remove_prepare_batch,
)


def record_prepare_batch(settings, batch):
    record = settings.prepare_batches.add()
    record.original_active = batch["original_active"]
    record.view_layer = batch["view_layer"]

    for obj in batch["original_selection"]:
        record.selection.add().object_ref = obj

    for source, duplicate in batch["copies"].items():
        entry = record.entries.add()
        entry.source = source
        entry.duplicate = duplicate

        visibility = batch["original_visibility"][source]
        entry.original_hide_viewport = visibility[0]
        entry.original_hide_render = visibility[1]
        entry.original_hide_select = visibility[2]
        entry.original_hidden = visibility[3]


def store_prepare_results(context, records, status, message):
    """Replace the last report with snapshots of this operation."""
    settings = context.scene.geprep
    settings.prepare_results.clear()
    context.window_manager.geprep_ui.prepare_results_expanded = True

    for source, copy_name, duplicate in records:
        entry = settings.prepare_results.add()
        entry.source = source
        entry.duplicate = duplicate
        entry.original_name = source.name if source else "(Missing original)"
        entry.copy_name = copy_name
        entry.status = status
        entry.message = message


class GEPREP_OT_prepare_copy(bpy.types.Operator):
    """Create prepared copies and hide their originals. Supports Undo."""

    bl_idname = "geprep.prepare_copy"
    bl_label = "Prepare Copy"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and bool(context.selected_objects)
        )

    def execute(self, context):
        settings = context.scene.geprep

        # Keep source references for reporting if preparation fails.
        failure_records = [
            (obj, "", None)
            for obj in context.selected_objects
        ]

        try:
            batch = prepare_assets(
                context,
                include_children=settings.prepare_include_children,
                use_sm_prefix=settings.prepare_use_sm_prefix,
                number_variants=settings.prepare_number_variants,
                duplicate_materials=settings.prepare_duplicate_materials,
                apply_rotation_scale=settings.prepare_apply_rotation_scale,
            )

        except PrepareRecoveryError as error:
            traceback.print_exc()
            store_prepare_results(
                context,
                failure_records,
                "INCOMPLETE",
                str(error),
            )
            self.report({"ERROR"}, str(error))
            return {"FINISHED"}

        except ValueError as error:
            store_prepare_results(
                context,
                failure_records,
                "SKIPPED",
                str(error),
            )
            self.report({"WARNING"}, str(error))
            return {"CANCELLED"}

        except Exception as error:
            traceback.print_exc()
            store_prepare_results(
                context,
                failure_records,
                "FAILED",
                f"No prepared copies kept. {error}",
            )
            self.report({"ERROR"}, f"Prepare failed: {error}")
            return {"CANCELLED"}

        records = [
            (source, duplicate.name, duplicate)
            for source, duplicate in batch["copies"].items()
        ]

        try:
            record_prepare_batch(settings, batch)

        except Exception as error:
            traceback.print_exc()
            message = (
                f"Copies were prepared, but recording their restoration "
                f"data failed: {error}. Use Undo before continuing"
            )
            store_prepare_results(
                context,
                records,
                "INCOMPLETE",
                message,
            )
            self.report({"ERROR"}, message)
            return {"FINISHED"}

        store_prepare_results(
            context,
            records,
            "PREPARED",
            "Working copy created. Original hidden",
        )

        meshes = sum(
            source.type == "MESH"
            for source in batch["copies"]
        )
        empties = len(batch["copies"]) - meshes

        self.report(
            {"INFO"},
            f"Prepared {meshes} mesh copies and {empties} Empty copies. "
            "Originals hidden",
        )
        return {"FINISHED"}


class GEPREP_OT_remove_prepared_copies(bpy.types.Operator):
    """Remove selected prepared copies and restore their originals."""

    bl_idname = "geprep.remove_prepared_copies"
    bl_label = "Remove Prepared Copies"
    bl_description = (
        "Remove selected prepared copies and restore their originals"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and bool(
                find_selected_prepare_batches(
                    context,
                    context.scene.geprep.prepare_batches,
                )
            )
        )

    def execute(self, context):
        settings = context.scene.geprep
        batches = settings.prepare_batches
        indices = find_selected_prepare_batches(context, batches)

        if len(indices) != 1:
            self.report(
                {"WARNING"},
                "Select prepared copies from one batch at a time",
            )
            return {"CANCELLED"}

        index = indices[0]

        # Snapshot only the copies selected for removal.
        selected = set(context.selected_objects)

        records = [
            (
                entry.source,
                entry.duplicate.name,
                None,
            )
            for entry in batches[index].entries
            if entry.duplicate is not None
            and entry.duplicate in selected
        ]

        try:
            removed = remove_prepare_batch(context, batches, index)

        except ValueError as error:
            store_prepare_results(
                context,
                records,
                "SKIPPED",
                str(error),
            )
            self.report({"WARNING"}, str(error))
            return {"CANCELLED"}

        except PrepareRecoveryError as error:
            traceback.print_exc()
            store_prepare_results(
                context,
                records,
                "INCOMPLETE",
                str(error),
            )
            self.report({"ERROR"}, str(error))
            return {"FINISHED"}

        store_prepare_results(
            context,
            records,
            "RESTORED",
            "Prepared copy removed if present. Original visibility restored",
        )

        self.report(
            {"INFO"},
            f"Removed {removed} prepared copies and restored their originals",
        )
        return {"FINISHED"}

import traceback

import bpy

from ..operations.prepare import (
    PrepareRecoveryError,
    prepare_assets,
    remove_last_prepare_batch,
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
            self.report({"ERROR"}, str(error))

            # Recovery was incomplete. Preserve Undo.
            return {"FINISHED"}

        except ValueError as error:
            self.report({"WARNING"}, str(error))
            return {"CANCELLED"}

        except Exception as error:
            traceback.print_exc()
            self.report({"ERROR"}, f"Prepare failed: {error}")
            return {"CANCELLED"}

        try:
            record_prepare_batch(settings, batch)

        except Exception as error:
            traceback.print_exc()
            self.report(
                {"ERROR"},
                f"Copies were prepared, but recording their restoration "
                f"data failed: {error}. Use Undo before continuing",
            )

            # Preparation already changed the scene. Preserve Undo.
            return {"FINISHED"}

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
    """Remove the latest prepared batch and restore its originals."""

    bl_idname = "geprep.remove_prepared_copies"
    bl_label = "Remove Prepared Copies"
    bl_description = (
        "Remove the most recently prepared batch and restore its originals"
    )
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and bool(context.scene.geprep.prepare_batches)
        )

    def execute(self, context):
        try:
            removed = remove_last_prepare_batch(
                context,
                context.scene.geprep.prepare_batches,
            )

        except ValueError as error:
            self.report({"WARNING"}, str(error))
            return {"CANCELLED"}

        except PrepareRecoveryError as error:
            traceback.print_exc()
            self.report({"ERROR"}, str(error))

            # Changes may already have happened. Preserve Undo.
            return {"FINISHED"}

        self.report(
            {"INFO"},
            f"Removed {removed} prepared copies and restored their originals",
        )
        return {"FINISHED"}

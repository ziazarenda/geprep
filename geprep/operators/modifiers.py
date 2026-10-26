import bpy
import traceback

from ..operations.modifiers import (
    ModifierRecoveryError,
    apply_object_modifiers,
)

class GEPREP_OT_toggle_modifier_preview(bpy.types.Operator):
    """Expand or collapse an object's modifier preview."""

    bl_idname = "geprep.toggle_modifier_preview"
    bl_label = "Toggle Modifier Preview"
    bl_options = {"INTERNAL"}

    object_key: bpy.props.StringProperty(
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context):
        obj = next(
            (
                obj
                for obj in context.selected_objects
                if str(obj.as_pointer()) == self.object_key
            ),
            None,
        )

        if obj is None:
            return {"CANCELLED"}

        previews = context.scene.geprep.modifier_previews

        # Remove entries whose objects have been deleted.
        for index in reversed(range(len(previews))):
            if previews[index].object_ref is None:
                previews.remove(index)

        entry = next(
            (
                entry
                for entry in previews
                if entry.object_ref == obj
            ),
            None,
        )

        if entry is None:
            entry = previews.add()
            entry.object_ref = obj

        entry.expanded = not entry.expanded

        if context.area is not None:
            context.area.tag_redraw()

        return {"FINISHED"}


class GEPREP_OT_apply_modifiers(bpy.types.Operator):
    """Apply viewport-enabled modifiers and keep disabled ones. Supports Undo."""

    bl_idname = "geprep.apply_modifiers"
    bl_label = "Apply Modifiers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and any(
                obj.type == "MESH"
                for obj in context.selected_objects
            )
        )

    def execute(self, context):
        settings = context.scene.geprep
        objects = sorted(
            (
                obj
                for obj in context.selected_objects
                if obj.type == "MESH"
            ),
            key=lambda obj: (obj.name.casefold(), obj.name),
        )

        results = settings.modifier_results
        results.clear()
        settings.modifier_results_expanded = True

        recovery_failed = False

        for obj in objects:
            entry = results.add()
            entry.object_ref = obj
            entry.object_name = obj.name
            entry.disabled = sum(
                not modifier.show_viewport
                for modifier in obj.modifiers
            )

            if recovery_failed:
                entry.status = "SKIPPED"
                entry.message = (
                    "Not processed because recovery failed on "
                    "an earlier object. Use Undo before continuing"
                )
                continue

            try:
                count = apply_object_modifiers(context, obj)

            except ModifierRecoveryError as error:
                traceback.print_exc()
                entry.status = "INCOMPLETE"
                entry.message = str(error)
                recovery_failed = True

            except ValueError as error:
                entry.status = "SKIPPED"
                entry.message = str(error)

            except Exception as error:
                traceback.print_exc()
                entry.status = "FAILED"
                entry.message = (
                    f"Applying modifiers failed. "
                    f"Object restored. {error}"
                )

            else:
                entry.applied = count

                if count:
                    entry.status = "APPLIED"
                    entry.message = ""
                else:
                    entry.status = "SKIPPED"
                    entry.message = "No viewport-enabled modifiers"

        applied = sum(entry.applied for entry in results)
        succeeded = sum(
            entry.status == "APPLIED"
            for entry in results
        )
        skipped = sum(
            entry.status == "SKIPPED"
            for entry in results
        )
        failed = sum(
            entry.status == "FAILED"
            for entry in results
        )
        incomplete = sum(
            entry.status == "INCOMPLETE"
            for entry in results
        )

        severity = (
            "ERROR"
            if incomplete
            else "WARNING"
            if failed or skipped
            else "INFO"
        )

        self.report(
            {severity},
            f"Applied {applied} modifiers on {succeeded} meshes. "
            f"{skipped} skipped, {failed} failed, "
            f"{incomplete} recovery failed",
        )

        # Keep successful changes and incomplete recovery undoable.
        return {"FINISHED"}

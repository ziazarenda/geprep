import traceback

import bpy

from ..operations.naming import (
    RenameRecoveryError,
    assign_object_name,
    plan_renames,
)


def record_naming_result(results, obj, original_name, status, message=""):
    entry = results.add()
    entry.object_ref = obj
    entry.original_name = original_name
    entry.resulting_name = obj.name
    entry.status = status
    entry.message = message


class GEPREP_OT_rename_objects(bpy.types.Operator):
    """Rename selected objects. Supports Undo."""

    bl_idname = "geprep.rename_objects"
    bl_label = "Rename Objects"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("NEW", "Set New Name", "Rename selected objects"),
            ("REPLACE", "Find & Replace", "Replace case-sensitive text"),
            ("SUFFIX", "Remove Numeric Suffix", "Remove trailing .001-style numbers"),
        ),
        default="NEW",
        options={"HIDDEN"},
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and bool(context.selected_objects)
        )

    def execute(self, context):
        settings = context.scene.geprep
        selected = list(context.selected_objects)

        objects = {}
        excluded = []

        for obj in selected:
            if obj.library is not None:
                excluded.append((obj, "This object is linked. Make it local first"))
            elif obj.override_library is not None:
                excluded.append((obj, "This object is a library override. Use a local copy"))
            elif not obj.is_editable:
                excluded.append((obj, "This object cannot be edited"))
            else:
                objects[obj.name] = obj

        try:
            plans = plan_renames(
                objects.keys(),
                (
                    obj.name
                    for obj in bpy.data.objects
                    if obj.library is None
                ),
                self.action,
                new_name=settings.name_new,
                find=settings.name_find,
                replacement=settings.name_replace,
            )
        except ValueError as error:
            self.report({"WARNING"}, str(error))
            return {"CANCELLED"}

        results = settings.naming_results
        results.clear()
        context.window_manager.geprep_ui.naming_results_expanded = True

        for obj, message in excluded:
            record_naming_result(
                results, obj, obj.name, "SKIPPED", message
            )

        stopped = False

        for plan in plans:
            obj = objects[plan["old"]]
            status = plan["status"]
            message = plan["message"]

            if stopped:
                status = "SKIPPED"
                message = (
                    "Not renamed. Stopped because the previous object's "
                    "original name could not be restored"
                )

            elif status == "CHANGED":
                try:
                    assign_object_name(obj, plan["new"])

                except RenameRecoveryError as error:
                    traceback.print_exc()
                    status = "INCOMPLETE"
                    message = str(error)
                    stopped = True

                except Exception as error:
                    traceback.print_exc()
                    status = "FAILED"
                    message = str(error)

            record_naming_result(
                results,
                obj,
                plan["old"],
                status,
                message,
            )

        changed = sum(entry.status == "CHANGED" for entry in results)
        skipped = sum(entry.status == "SKIPPED" for entry in results)
        failed = sum(entry.status == "FAILED" for entry in results)
        incomplete = sum(entry.status == "INCOMPLETE" for entry in results)

        severity = (
            {"ERROR"} if incomplete
            else {"WARNING"} if failed
            else {"INFO"}
        )

        summary = (
            f"Naming: {changed} renamed, {skipped} skipped, "
            f"{failed} failed, {incomplete} incomplete"
        )

        if incomplete:
            summary += ". Use Undo before continuing"

        self.report(severity, summary)

        # Preserve Undo even if some renames failed after others succeeded.
        return {"FINISHED"}

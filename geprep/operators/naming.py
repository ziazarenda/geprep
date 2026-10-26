import traceback

import bpy

from ..operations.naming import (
    RenameRecoveryError,
    assign_object_name,
    plan_renames,
)


class GEPREP_OT_rename_objects(bpy.types.Operator):
    """Rename selected objects. Supports Undo."""

    bl_idname = "geprep.rename_objects"
    bl_label = "Rename Objects"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            ("BASE", "Set Base Name", "Rename selected objects"),
            ("REPLACE", "Find & Replace", "Replace case-sensitive text"),
            ("SUFFIX", "Remove Numeric Suffix", "Remove trailing .001-style numbers"),
        ),
        default="BASE",
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

        objects = {
            obj.name: obj
            for obj in selected
            if obj.library is None
            and obj.override_library is None
            and obj.is_editable
        }

        skipped = len(selected) - len(objects)

        if not objects:
            self.report({"WARNING"}, "Select editable local objects")
            return {"CANCELLED"}

        try:
            plans = plan_renames(
                objects.keys(),
                (
                    obj.name
                    for obj in bpy.data.objects
                    if obj.library is None
                ),
                self.action,
                base=settings.name_base,
                find=settings.name_find,
                replacement=settings.name_replace,
            )
        except ValueError as error:
            self.report({"WARNING"}, str(error))
            return {"CANCELLED"}

        changed = 0
        failed = 0

        for index, plan in enumerate(plans):
            if plan["status"] != "CHANGED":
                skipped += 1
                continue

            obj = objects[plan["old"]]

            try:
                assign_object_name(obj, plan["new"])

            except RenameRecoveryError as error:
                traceback.print_exc()
                self.report({"ERROR"}, str(error))

                # Stop if recovery failed. Remaining objects are untouched.
                failed += 1
                skipped += len(plans) - index - 1
                break

            except Exception as error:
                traceback.print_exc()
                self.report(
                    {"WARNING"},
                    f"Could not rename {plan['old']!r}: {error}",
                )
                failed += 1

            else:
                changed += 1

        self.report(
            {"WARNING"} if failed else {"INFO"},
            f"Naming: {changed} renamed, {skipped} skipped, {failed} failed",
        )

        # Preserve Undo even if some renames failed after others succeeded.
        return {"FINISHED"}

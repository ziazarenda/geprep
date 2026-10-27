import traceback

import bpy

from ..operations.checker import (
    CheckerRecoveryError,
    apply_checker_preview,
    has_checker_preview,
    restore_checker_previews,
)


class GEPREP_OT_checker_preview(bpy.types.Operator):
    """Show a UV checker and save the original material assignments."""

    bl_idname = "geprep.checker_preview"
    bl_label = "Checker"
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

        shown = skipped = failed = 0

        for obj in objects:
            try:
                apply_checker_preview(
                    context,
                    obj,
                    uv_name=settings.uv_map_name,
                    width=settings.uv_texture_width,
                    height=settings.uv_texture_height,
                )

            except CheckerRecoveryError as error:
                traceback.print_exc()
                self.report({"ERROR"}, str(error))
                return {"FINISHED"}

            except ValueError as error:
                skipped += 1
                self.report({"WARNING"}, f"{obj.name}: {error}")

            except Exception as error:
                traceback.print_exc()
                failed += 1
                self.report({"WARNING"}, f"{obj.name}: {error}")

            else:
                shown += 1

        if (
            shown
            and context.area is not None
            and context.area.type == "VIEW_3D"
        ):
            context.space_data.shading.type = "MATERIAL"

        self.report(
            {"WARNING"} if skipped or failed else {"INFO"},
            f"Checker: {shown} shown, {skipped} skipped, {failed} failed",
        )

        return {"FINISHED"} if shown else {"CANCELLED"}


class GEPREP_OT_restore_checker(bpy.types.Operator):
    """Restore the original materials on selected checker objects."""

    bl_idname = "geprep.restore_checker"
    bl_label = "Remove Checker"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if context.mode != "OBJECT" or not context.scene.is_editable:
            return False

        return any(
            has_checker_preview(obj)
            for obj in context.selected_objects
        )

    def execute(self, context):
        restored, errors = restore_checker_previews(
            context,
            objects=context.selected_objects,
        )

        for message in errors:
            self.report({"ERROR"}, message)

        self.report(
            {"WARNING"} if errors else {"INFO"},
            f"Checker: {restored} previews removed, "
            f"{len(errors)} errors",
        )

        return {"FINISHED"}

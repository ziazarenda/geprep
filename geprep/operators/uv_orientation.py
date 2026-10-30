import traceback

import bmesh
import bpy
import numpy as np

from ..helpers.progress import with_progress
from ..operations.uv_orientation import (
    MIRROR_ACTION,
    ORIENTATION_ACTIONS,
    plan_uv_orientation,
)

ALL_ACTIONS = ORIENTATION_ACTIONS + (MIRROR_ACTION,)


class GEPREP_OT_orient_uvs(bpy.types.Operator):
    """Rotate whole UV islands touched by the selected faces."""

    bl_idname = "geprep.orient_uvs"
    bl_label = "Orient UVs"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=ALL_ACTIONS,
        default="ALIGN",
        options={"HIDDEN", "SKIP_SAVE"},
    )

    @classmethod
    def description(cls, context, properties):
        return next(
            tooltip
            for key, _, tooltip in ALL_ACTIONS
            if key == properties.action
        )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "EDIT_MESH"
            and context.scene.is_editable
        )

    def execute(self, context):
        settings = context.scene.geprep
        size = np.array(
            (settings.uv_texture_width, settings.uv_texture_height),
            dtype=float,
        )

        objects = sorted(
            (
                obj
                for obj in context.objects_in_mode_unique_data
                if obj.type == "MESH"
            ),
            key=lambda obj: (obj.name.casefold(), obj.name),
        )

        changed = islands = selected_total = failed = 0
        failures = []

        for obj in with_progress(context, objects):
            changes = []

            try:
                if (
                    not obj.is_editable
                    or not obj.data.is_editable
                    or obj.library is not None
                    or obj.override_library is not None
                ):
                    raise ValueError("Use an editable local object and mesh")

                bm = bmesh.from_edit_mesh(obj.data)
                name = settings.uv_map_name.strip()

                if not name and bm.loops.layers.uv.active is not None:
                    name = bm.loops.layers.uv.active.name

                changes, count, selected_count = plan_uv_orientation(
                    obj,
                    bm,
                    name,
                    size,
                    self.action,
                    settings.uv_orientation_reference,
                    settings.uv_orientation_tolerance,
                )
                selected_total += selected_count

                for data, _, new in changes:
                    data.uv = new

                bmesh.update_edit_mesh(
                    obj.data,
                    loop_triangles=False,
                    destructive=False,
                )

                if count:
                    changed += 1
                    islands += count

            except Exception as error:
                if not isinstance(error, ValueError):
                    traceback.print_exc()

                # Roll back anything written before the failure.
                for data, old, _ in changes:
                    data.uv = old

                if changes:
                    bmesh.update_edit_mesh(
                        obj.data,
                        loop_triangles=False,
                        destructive=False,
                    )

                failed += 1
                failures.append(f"{obj.name}: {error}")

                if len(objects) > 1:
                    self.report({"WARNING"}, failures[-1])

        if changed:
            # Mirrored and orientation findings no longer match the UVs.
            settings.uv_results.clear()

        if not changed and len(failures) == 1:
            self.report({"WARNING"}, failures[0])

        elif changed or failed:
            if self.action == "MIRROR":
                summary = (
                    f"Fixed mirroring on {islands} island(s) on "
                    f"{changed} mesh(es), {failed} failed"
                )

            else:
                summary = (
                    f"Oriented {islands} island(s) on {changed} mesh(es), "
                    f"{failed} failed. Repack if islands now overlap"
                )

            self.report({"WARNING"} if failed else {"INFO"}, summary)

        elif selected_total:
            self.report({"INFO"}, "No mirrored islands in the selection")

        else:
            self.report({"INFO"}, "Select faces in Edit Mode first")

        return {"FINISHED"} if changed else {"CANCELLED"}

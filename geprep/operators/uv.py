import traceback

import bpy

from ..helpers.objects import (
    find_object_by_key,
    has_selected_mesh,
    selected_meshes,
)
from ..helpers.progress import with_progress
from ..operations.mesh import (
    MeshFixRecoveryError,
    select_mesh_elements,
)
from ..operations.uv import (
    UV_FINDINGS,
    apply_uv_density,
    inspect_uv_mesh,
)


def run_uv_check(context, objects):
    """Inspect the base-mesh UVs of `objects` and store the results.

    Returns (passed, inspect, failed) counts.
    """
    settings = context.scene.geprep

    context.view_layer.update()

    width = settings.uv_texture_width
    height = settings.uv_texture_height
    target = settings.uv_target_density
    tolerance = settings.uv_tolerance
    unit_scale = context.scene.unit_settings.scale_length

    results = settings.uv_results
    results.clear()

    settings.uv_checked_width = width
    settings.uv_checked_height = height
    settings.uv_checked_target = target
    settings.uv_checked_tolerance = tolerance
    settings.uv_checked_units = unit_scale

    context.window_manager.geprep_ui.uv_results_expanded = True

    for obj in with_progress(context, objects):
        entry = results.add()
        entry.object_ref = obj
        entry.object_name = obj.name

        try:
            result = inspect_uv_mesh(
                obj.data,
                obj.matrix_world,
                unit_scale,
                uv_name=settings.uv_map_name,
                width=width,
                height=height,
                target=target,
                tolerance=tolerance,
            )

            entry.uv_name = result["uv_name"]
            entry.density_available = result["density"] is not None

            if entry.density_available:
                entry.density = result["density"]
                entry.minimum_density = result["minimum_density"]
                entry.maximum_density = result["maximum_density"]

            entry.tile_coverage = result["coverage"]
            entry.islands = len(result["islands"])
            entry.mismatched_islands = len(
                result["mismatched_islands"]
            )
            entry.unmeasurable_islands = len(
                result["unmeasurable_islands"]
            )

            for key, faces in result["findings"].items():
                setattr(entry, f"{key}_faces", len(faces))

            entry.status = (
                "INSPECT"
                if any(result["findings"].values())
                else "PASSED"
            )

        except Exception as error:
            traceback.print_exc()
            entry.status = "FAILED"
            entry.message = str(error)

    passed = sum(
        entry.status == "PASSED"
        for entry in results
    )
    inspect = sum(
        entry.status == "INSPECT"
        for entry in results
    )
    failed = sum(
        entry.status == "FAILED"
        for entry in results
    )

    return passed, inspect, failed


class GEPREP_OT_check_uvs(bpy.types.Operator):
    """Inspect base-mesh UVs. Shader tiling is not measured. Overlap is estimated on a 512 × 512 grid. Findings may be intentional."""

    bl_idname = "geprep.check_uvs"
    bl_label = "Check UVs"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and has_selected_mesh(context)
        )

    def execute(self, context):
        passed, inspect, failed = run_uv_check(
            context,
            selected_meshes(context),
        )

        self.report(
            {"WARNING"} if failed else {"INFO"},
            f"UV check: {passed} without findings, "
            f"{inspect} to inspect, {failed} failed",
        )

        return {"FINISHED"}


class GEPREP_OT_select_uv_finding(bpy.types.Operator):
    """Select faces matching this UV finding in Edit Mode."""

    bl_idname = "geprep.select_uv_finding"
    bl_label = "Select UV Finding"
    bl_options = {"REGISTER", "UNDO"}

    object_key: bpy.props.StringProperty(
        options={"HIDDEN", "SKIP_SAVE"},
    )

    finding: bpy.props.EnumProperty(
        items=tuple(
            (key, label, "")
            for key, label in UV_FINDINGS
        ),
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.area is not None
            and context.area.type == "VIEW_3D"
            and context.scene.is_editable
        )

    def execute(self, context):
        obj = find_object_by_key(
            context.view_layer.objects,
            self.object_key,
        )

        if obj is None or obj.type != "MESH":
            self.report({"WARNING"}, "The mesh is no longer available")
            return {"CANCELLED"}

        if (
            not obj.is_editable
            or not obj.data.is_editable
            or obj.override_library is not None
        ):
            self.report(
                {"WARNING"},
                "Use an editable local object and mesh",
            )
            return {"CANCELLED"}

        if obj.hide_select or not obj.visible_get(
            view_layer=context.view_layer,
            viewport=context.space_data,
        ):
            self.report(
                {"WARNING"},
                "Show the object and enable selection first",
            )
            return {"CANCELLED"}

        settings = context.scene.geprep
        entry = next(
            (
                entry
                for entry in settings.uv_results
                if entry.object_ref == obj
            ),
            None,
        )

        if entry is None or entry.status == "FAILED":
            self.report({"WARNING"}, "Run Check UVs again first")
            return {"CANCELLED"}

        try:
            context.view_layer.update()

            result = inspect_uv_mesh(
                obj.data,
                obj.matrix_world,
                settings.uv_checked_units,
                uv_name=entry.uv_name,
                width=settings.uv_checked_width,
                height=settings.uv_checked_height,
                target=settings.uv_checked_target,
                tolerance=settings.uv_checked_tolerance,
            )
            indices = result["findings"][self.finding]

        except Exception as error:
            traceback.print_exc()
            self.report({"ERROR"}, f"Could not inspect UVs: {error}")
            return {"CANCELLED"}

        if not indices:
            self.report(
                {"INFO"},
                "No matching faces remain. Run Check UVs again",
            )
            return {"CANCELLED"}

        previous_selection = list(context.selected_objects)
        previous_active = context.view_layer.objects.active
        previous_mode = tuple(context.tool_settings.mesh_select_mode)
        previous_uv_index = obj.data.uv_layers.active_index
        entered_edit_mode = False

        try:
            for selected in previous_selection:
                selected.select_set(False)

            obj.select_set(True)
            context.view_layer.objects.active = obj
            context.tool_settings.mesh_select_mode = (False, False, True)

            obj.data.uv_layers.active_index = obj.data.uv_layers.find(
                entry.uv_name
            )

            result = bpy.ops.object.mode_set(mode="EDIT")
            entered_edit_mode = obj.mode == "EDIT"

            if "FINISHED" not in result or not entered_edit_mode:
                raise RuntimeError("Could not enter Edit Mode")

            select_mesh_elements(obj.data, indices, "FACE")

        except Exception as error:
            traceback.print_exc()

            if entered_edit_mode:
                self.report(
                    {"ERROR"},
                    f"Face selection failed: {error}. Use Undo",
                )
                return {"FINISHED"}

            try:
                obj.data.uv_layers.active_index = previous_uv_index

                for selected in list(context.selected_objects):
                    selected.select_set(False)

                for selected in previous_selection:
                    selected.select_set(True)

                context.view_layer.objects.active = previous_active
                context.tool_settings.mesh_select_mode = previous_mode

            except Exception as recovery_error:
                traceback.print_exc()
                self.report(
                    {"ERROR"},
                    f"Selection failed: {error}. "
                    f"Could not restore selection: {recovery_error}. "
                    "Use Undo",
                )
                return {"FINISHED"}

            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        self.report(
            {"INFO"},
            f"Selected {len(indices)} faces. "
            "Return to Object Mode to select another finding",
        )
        return {"FINISHED"}


class GEPREP_OT_set_uv_density(bpy.types.Operator):
    """Resize base-mesh UV islands to the target density. May create overlaps or move UVs outside the tile. Repack without rescaling if needed. Supports Undo."""

    bl_idname = "geprep.set_uv_density"
    bl_label = "Set Density"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and has_selected_mesh(context)
        )

    def execute(self, context):
        settings = context.scene.geprep
        objects = selected_meshes(context)

        results = settings.uv_density_results
        results.clear()
        context.window_manager.geprep_ui.uv_density_results_expanded = True

        recovery_failed = False

        for obj in with_progress(context, objects):
            entry = results.add()
            entry.object_ref = obj
            entry.object_name = obj.name

            if recovery_failed:
                entry.status = "SKIPPED"
                entry.message = (
                    "Not processed because recovery failed on "
                    "an earlier object. Use Undo before continuing"
                )
                continue

            try:
                changed, message = apply_uv_density(
                    context,
                    obj,
                    uv_name=settings.uv_map_name,
                    width=settings.uv_texture_width,
                    height=settings.uv_texture_height,
                    target=settings.uv_target_density,
                )

            except MeshFixRecoveryError as error:
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
                    f"Setting density failed. "
                    f"Original mesh retained or restored. {error}"
                )

            else:
                entry.status = "CHANGED" if changed else "SKIPPED"
                entry.message = message

        changed_count = sum(
            entry.status == "CHANGED"
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

        if changed_count or incomplete:
            settings.uv_results.clear()

        if changed_count and not incomplete:
            try:
                run_uv_check(context, selected_meshes(context))

            except Exception as error:
                traceback.print_exc()
                settings.uv_results.clear()
                self.report(
                    {"WARNING"},
                    f"UVs updated, but automatic recheck failed: {error}",
                )

        severity = (
            "ERROR"
            if incomplete
            else "WARNING"
            if failed
            else "INFO"
        )

        self.report(
            {severity},
            f"Set Density: {changed_count} changed, "
            f"{skipped} skipped, {failed} failed, "
            f"{incomplete} recovery failed",
        )

        return {"FINISHED"}

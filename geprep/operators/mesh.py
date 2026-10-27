import traceback

import bpy

from functools import partial

from ..operations.mesh import (
    MESH_FINDINGS,
    MeshFixRecoveryError,
    apply_mesh_fix,
    build_dissolve_degenerate_mesh,
    build_triangulate_mesh,
    build_recalculate_normals_mesh,
    build_merge_by_distance_mesh,
    build_remove_loose_mesh,
    inspect_base_mesh,
    select_mesh_elements,
)


def update_mesh_finding_view(context):
    """Adjust the viewport after selecting finding geometry."""
    ui = context.window_manager.geprep_ui
    warnings = []

    if ui.mesh_xray_selection:
        shading = context.space_data.shading

        if shading.type == "SOLID":
            shading.show_xray = True

        elif shading.type == "WIREFRAME":
            shading.show_xray_wireframe = True

        else:
            warnings.append(
                "X-Ray requires Solid or Wireframe shading"
            )

    if ui.mesh_zoom_selection:
        region = next(
            (
                region
                for region in context.area.regions
                if region.type == "WINDOW"
            ),
            None,
        )

        if region is None:
            warnings.append("No viewport region available for zoom")
        else:
            try:
                context.view_layer.update()

                with context.temp_override(region=region):
                    result = bpy.ops.view3d.view_selected(
                        use_all_regions=False,
                    )

                if "FINISHED" not in result:
                    warnings.append(
                        "Blender could not frame the selected geometry"
                    )

            except Exception as error:
                warnings.append(
                    f"Could not frame the selected geometry: {error}"
                )

    return warnings


class GEPREP_OT_check_mesh(bpy.types.Operator):
    """Inspect base geometry without modifiers. Recheck after geometry or transform changes. Findings may be intentional."""

    bl_idname = "geprep.check_mesh"
    bl_label = "Check Mesh"
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

        context.view_layer.update()

        distance = settings.mesh_distance
        unit_scale = context.scene.unit_settings.scale_length

        results = settings.mesh_results
        results.clear()

        settings.mesh_checked_distance = distance
        settings.mesh_checked_units = unit_scale
        context.window_manager.geprep_ui.mesh_results_expanded = True

        for obj in objects:
            entry = results.add()
            entry.object_ref = obj
            entry.object_name = obj.name

            try:
                found, totals = inspect_base_mesh(
                    obj.data,
                    obj.matrix_world,
                    unit_scale,
                    distance,
                )

                for key, indices in found.items():
                    setattr(entry, key, len(indices))

                (
                    entry.vertices,
                    entry.edges,
                    entry.faces,
                    entry.triangles,
                ) = totals

                if not entry.vertices:
                    entry.status = "INSPECT"
                    entry.message = "Mesh is empty"

                elif any(found.values()):
                    entry.status = "INSPECT"

                else:
                    entry.status = "PASSED"

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

        self.report(
            {"WARNING"} if failed else {"INFO"},
            f"Mesh check: {passed} without findings, "
            f"{inspect} to inspect, {failed} failed",
        )

        return {"FINISHED"}


class GEPREP_OT_select_mesh_finding(bpy.types.Operator):
    """Select matching geometry in Edit Mode. Reveal matching hidden elements."""

    bl_idname = "geprep.select_mesh_finding"
    bl_label = "Select Finding"
    bl_options = {"REGISTER", "UNDO"}

    object_key: bpy.props.StringProperty(
        options={"HIDDEN", "SKIP_SAVE"},
    )

    finding: bpy.props.EnumProperty(
        items=tuple(
            (key, label, "")
            for key, label, _ in MESH_FINDINGS
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
        obj = next(
            (
                obj
                for obj in context.view_layer.objects
                if str(obj.as_pointer()) == self.object_key
            ),
            None,
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

        try:
            context.view_layer.update()

            found, _ = inspect_base_mesh(
                obj.data,
                obj.matrix_world,
                settings.mesh_checked_units,
                settings.mesh_checked_distance,
            )
            indices = found[self.finding]

        except Exception as error:
            traceback.print_exc()
            self.report({"ERROR"}, f"Could not inspect mesh: {error}")
            return {"CANCELLED"}

        if not indices:
            self.report(
                {"INFO"},
                "No matching geometry remains. Run Check Mesh again",
            )
            return {"CANCELLED"}

        mode = next(
            mode
            for key, _, mode in MESH_FINDINGS
            if key == self.finding
        )

        previous_selection = list(context.selected_objects)
        previous_active = context.view_layer.objects.active
        previous_mode = tuple(context.tool_settings.mesh_select_mode)
        entered_edit_mode = False

        try:
            for selected in previous_selection:
                selected.select_set(False)

            obj.select_set(True)
            context.view_layer.objects.active = obj
            context.tool_settings.mesh_select_mode = (
                mode == "VERT",
                mode == "EDGE",
                mode == "FACE",
            )

            result = bpy.ops.object.mode_set(mode="EDIT")
            entered_edit_mode = obj.mode == "EDIT"

            if "FINISHED" not in result or not entered_edit_mode:
                raise RuntimeError("Could not enter Edit Mode")

            select_mesh_elements(obj.data, indices, mode)

        except Exception as error:
            traceback.print_exc()

            if entered_edit_mode:
                self.report(
                    {"ERROR"},
                    f"Geometry selection failed: {error}. Use Undo",
                )
                return {"FINISHED"}

            try:
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

        try:
            for warning in update_mesh_finding_view(context):
                self.report({"WARNING"}, warning)

        except Exception as error:
            traceback.print_exc()
            self.report(
                {"WARNING"},
                f"Geometry selected, but viewport adjustment failed: {error}",
            )

        self.report(
            {"INFO"},
            f"Selected {len(indices)} elements. "
            "Return to Object Mode to select another finding",
        )
        return {"FINISHED"}


class GEPREP_OT_mesh_fix(bpy.types.Operator):
    """Apply a mesh fix to selected objects. Supports Undo."""

    bl_idname = "geprep.mesh_fix"
    bl_label = "Mesh Fix"
    bl_options = {"REGISTER", "UNDO"}

    action: bpy.props.EnumProperty(
        items=(
            (
                "LOOSE",
                "Remove Loose Geometry",
                "Remove isolated vertices and edges without faces",
            ),
            (
                "MERGE",
                "Merge by Distance",
                "Merge nearby vertices; may change faces, UVs, and seams",
            ),
            (
                "NORMALS",
                "Recalculate Normals Outside",
                "Reorient faces; inspect open surfaces manually",
            ),
            (
                "TRIANGULATE",
                "Triangulate",
                "Split quads and n-gons into triangles",
            ),
            (
                "DEGENERATE",
                "Dissolve Degenerate Geometry",
                "Collapse short edges and dissolve degenerate faces",
            ),
        ),
        default="LOOSE",
    )

    @classmethod
    def description(cls, context, properties):
        descriptions = {
            "LOOSE": (
                "Remove isolated vertices and edges without faces. "
                "Supports Undo"
            ),
            "MERGE": (
                "Merge vertices within the configured distance. "
                "May change faces, UVs, and seams. Supports Undo"
            ),
            "NORMALS": (
                "Recalculate face winding outward. "
                "Inspect open surfaces manually. Supports Undo"
            ),
            "TRIANGULATE": (
                "Split quads and n-gons into triangles. Supports Undo"
            ),
            "DEGENERATE": (
                "Collapse short edges and dissolve degenerate faces. "
                "May change faces, UVs, and seams. Supports Undo"
            ),
        }

        return descriptions[properties.action]

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

        results = settings.mesh_fix_results
        results.clear()
        action_labels = {
            "LOOSE": "Remove Loose Geometry",
            "MERGE": "Merge by Distance",
            "NORMALS": "Recalculate Normals Outside",
            "TRIANGULATE": "Triangulate",
            "DEGENERATE": "Dissolve Degenerate Geometry",
        }
        settings.mesh_fix_action = action_labels[self.action]
        context.window_manager.geprep_ui.mesh_fix_results_expanded = True

        recovery_failed = False

        for obj in objects:
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
                if self.action in {"MERGE", "DEGENERATE"}:
                    if self.action == "MERGE":
                        builder = build_merge_by_distance_mesh
                        distance = settings.mesh_merge_distance
                    else:
                        builder = build_dissolve_degenerate_mesh
                        distance = settings.mesh_dissolve_distance

                    build_fix = partial(
                        builder,
                        matrix_world=obj.matrix_world.copy(),
                        unit_scale=context.scene.unit_settings.scale_length,
                        distance=distance,
                    )

                else:
                    builders = {
                        "LOOSE": build_remove_loose_mesh,
                        "NORMALS": build_recalculate_normals_mesh,
                        "TRIANGULATE": build_triangulate_mesh,
                    }
                    build_fix = builders[self.action]

                changed, message = apply_mesh_fix(
                    context,
                    obj,
                    build_fix,
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
                    f"Fix failed. Original mesh retained or restored. {error}"
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

        # Previous checks no longer describe the modified geometry.
        if changed_count or incomplete:
            settings.mesh_results.clear()

        if changed_count and not incomplete:
            try:
                result = bpy.ops.geprep.check_mesh()

                if "FINISHED" not in result:
                    raise RuntimeError("Blender did not finish the mesh check")

            except Exception as error:
                traceback.print_exc()
                settings.mesh_results.clear()
                self.report(
                    {"WARNING"},
                    f"Meshes updated, but automatic recheck failed: {error}",
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
            f"{settings.mesh_fix_action}: {changed_count} changed, "
            f"{skipped} skipped, {failed} failed, "
            f"{incomplete} recovery failed",
        )

        return {"FINISHED"}

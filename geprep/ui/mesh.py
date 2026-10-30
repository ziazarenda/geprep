import bpy

from ..operations.mesh import MESH_FINDINGS
from ..operators.mesh import MESH_FIX_ACTIONS
from .common import (
    INPUT_SCALE_Y,
    draw_action_button,
    draw_collapsible_box,
    draw_finding_select_button,
    draw_multiline_message,
    draw_result_item_header,
    draw_value_row,
)


# Mesh fixes that take a distance, and the setting that holds it.
MESH_FIX_DISTANCE_PROPS = {
    "MERGE": "mesh_merge_distance",
    "DEGENERATE": "mesh_dissolve_distance",
}


def draw_mesh_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.mesh_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "mesh_results_expanded",
        "Last Mesh Check",
        len(results),
    )
    if not expanded:
        return

    box.label(
        text=f"Check distance: {settings.mesh_checked_distance:g} m"
    )

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "mesh",
            index,
            entry.object_name,
            entry.status,
            entry.object_ref,
        )

        if not item_expanded:
            continue

        draw_multiline_message(item, context, entry.message)

        if entry.status == "FAILED":
            continue

        totals = item.column(align=True)

        for label, count in (
            ("Vertices", entry.vertices),
            ("Edges", entry.edges),
            ("Faces", entry.faces),
            ("Triangles", entry.triangles),
        ):
            draw_value_row(totals, label, count)

        item.separator()

        findings = item.column(align=True)

        for key, label, _ in MESH_FINDINGS:
            count = getattr(entry, key)
            row = draw_value_row(findings, label, count)

            if count:
                draw_finding_select_button(
                    row,
                    context,
                    entry.object_ref,
                    "geprep.select_mesh_finding",
                    key,
                )


def draw_mesh_fix_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.mesh_fix_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "mesh_fix_results_expanded",
        "Last Mesh Fix Results",
        len(results),
    )
    if not expanded:
        return

    box.label(text=settings.mesh_fix_action)

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "mesh_fixes",
            index,
            entry.object_name,
            entry.status,
            entry.object_ref,
        )

        if not item_expanded:
            continue

        draw_multiline_message(item, context, entry.message)


class GEPREP_PT_mesh(bpy.types.Panel):
    bl_idname = "GEPREP_PT_mesh"
    bl_label = "Mesh"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep
        ui = context.window_manager.geprep_ui

        check_box = layout.box()
        check_box.label(text="Geometry Check")
        col = check_box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(settings, "mesh_distance")

        draw_action_button(
            check_box,
            "geprep.check_mesh",
            "Check Mesh",
            icon="VIEWZOOM",
        )

        col = check_box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(ui, "mesh_zoom_selection")
        col.prop(ui, "mesh_xray_selection")

        draw_mesh_results(layout, settings, context)

        fixes_main, fixes_expanded = draw_collapsible_box(
            layout,
            ui,
            "mesh_fixes_expanded",
            "Mesh Fixes",
        )

        if fixes_expanded:
            for action, label, _ in MESH_FIX_ACTIONS:
                box = fixes_main.box()
                distance_prop = MESH_FIX_DISTANCE_PROPS.get(action)

                if distance_prop is not None:
                    col = box.column()
                    col.scale_y = INPUT_SCALE_Y
                    col.prop(settings, distance_prop)

                draw_action_button(
                    box,
                    "geprep.mesh_fix",
                    label,
                    action=action,
                )

        draw_mesh_fix_results(layout, settings, context)

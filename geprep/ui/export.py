import bpy

from .common import (
    INPUT_SCALE_Y,
    draw_action_button,
    draw_collapsible_box,
    draw_multiline_message,
    draw_nested_result_header,
)


def draw_export_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.export_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "export_results_expanded",
        "Last Export",
        len(results),
    )
    if not expanded:
        return

    counts = {
        status: sum(entry.status == status for entry in results)
        for status in ("EXPORTED", "SKIPPED", "FAILED")
    }
    box.label(
        text=(
            f"{counts['EXPORTED']} exported, {counts['SKIPPED']} skipped, "
            f"{counts['FAILED']} failed"
        )
    )

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status == "FAILED"

        if not draw_nested_result_header(
            item,
            context,
            "export",
            index,
            entry.filename,
            entry.status,
        ):
            continue

        draw_multiline_message(item, context, entry.message, 80)
        draw_multiline_message(item, context, entry.filepath, 80)


class GEPREP_PT_export(bpy.types.Panel):
    bl_idname = "GEPREP_PT_export"
    bl_label = "Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 7
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep

        box = layout.box()
        col = box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(settings, "export_folder")
        col.prop(settings, "export_mode")

        if settings.export_mode != "SEPARATE":
            col.prop(settings, "export_name")

        box.prop(settings, "export_materials")
        box.prop(settings, "export_tangents")
        box.prop(settings, "export_overwrite")

        draw_action_button(
            box,
            "geprep.export_glb",
            "Export GLB",
            icon="EXPORT",
        )
        box.label(text="Y up, scene unit scale applied", icon="INFO")

        draw_export_results(layout, settings, context)

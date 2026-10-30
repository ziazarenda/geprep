import bpy

from .common import (
    INPUT_SCALE_Y,
    draw_action_button,
    draw_collapsible_box,
    draw_multiline_message,
    draw_result_item_header,
)


def draw_prepare_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.prepare_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "prepare_results_expanded",
        "Last Prepare Results",
        len(results),
    )
    if not expanded:
        return

    for index, entry in enumerate(results):
        target = (
            entry.duplicate
            if entry.duplicate is not None
            else entry.source
        )
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "prepare",
            index,
            entry.original_name,
            entry.status,
            target,
        )

        if not item_expanded:
            continue

        item.label(text=f"Original: {entry.original_name}")

        if entry.copy_name:
            item.label(text=f"Copy: {entry.copy_name}")

        draw_multiline_message(item, context, entry.message)


class GEPREP_PT_prepare(bpy.types.Panel):
    bl_idname = "GEPREP_PT_prepare"
    bl_label = "Prepare"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 1

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep

        prep_box = layout.box()

        col = prep_box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(settings, "prepare_include_children")
        col.prop(settings, "prepare_use_sm_prefix")
        col.prop(settings, "prepare_number_variants")
        col.prop(settings, "prepare_duplicate_materials")
        col.prop(settings, "prepare_apply_rotation_scale")

        draw_action_button(prep_box, "geprep.prepare_copy", "Prepare Copy")

        draw_action_button(
            layout.box(),
            "geprep.remove_prepared_copies",
            "Remove Prepared Copies",
        )

        draw_prepare_results(layout, settings, context)

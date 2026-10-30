import bpy

from .common import (
    INPUT_SCALE_Y,
    draw_action_button,
    draw_collapsible_box,
    draw_multiline_message,
    draw_result_item_header,
)


def draw_naming_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.naming_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "naming_results_expanded",
        "Last Naming Results",
        len(results),
    )
    if not expanded:
        return

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "naming",
            index,
            entry.original_name,
            entry.status,
            entry.object_ref,
            status_label="Renamed" if entry.status == "CHANGED" else None,
        )

        if not item_expanded:
            continue

        item.label(text=f"Before: {entry.original_name}")
        item.label(text=f"After: {entry.resulting_name}")

        draw_multiline_message(item, context, entry.message)


class GEPREP_PT_naming(bpy.types.Panel):
    bl_idname = "GEPREP_PT_naming"
    bl_label = "Naming"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 0
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep

        box = layout.box()
        col = box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(settings, "name_new", text="Name")

        draw_action_button(
            box,
            "geprep.rename_objects",
            "Set New Name",
            action="NEW",
        )

        box = layout.box()
        col = box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(settings, "name_find", text="Replace")
        col.prop(settings, "name_replace", text="With")

        draw_action_button(
            box,
            "geprep.rename_objects",
            "Find & Replace",
            action="REPLACE",
        )

        draw_action_button(
            layout.box(),
            "geprep.rename_objects",
            "Remove Numeric Suffix",
            action="SUFFIX",
        )

        draw_naming_results(layout, settings, context)

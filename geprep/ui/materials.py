import bpy

from ..helpers.objects import pointer_key
from .common import (
    INPUT_SCALE_Y,
    draw_action_button,
    draw_collapsible_box,
    draw_multiline_message,
    draw_nested_result_header,
    draw_result_item_header,
    draw_value_row,
)


def draw_node_button(row, context, obj, material, texture):
    """Add the 'show this node in a Shader Editor' button to a texture row."""
    row.separator(factor=1.6)

    button_row = row.row(align=True)
    button_row.enabled = (
        context.mode == "OBJECT"
        and obj is not None
        and bool(texture.node_chain)
    )

    button = button_row.operator(
        "geprep.inspect_node",
        text="",
        icon="NODETREE",
    )
    button.object_key = pointer_key(obj)
    button.slot = material.slot
    button.material = material.name
    button.node_chain = texture.node_chain


def draw_texture_result(layout, context, texture, index, obj, material):
    box = layout.box()
    box.alert = texture.status == "FAILED"

    if not draw_nested_result_header(
        box,
        context,
        "material_texture",
        index,
        texture.name,
        texture.status,
        extra=lambda row: draw_node_button(row, context, obj, material, texture),
    ):
        return

    draw_multiline_message(box, context, texture.message, 96)

    details = box.column(align=True)

    if texture.width and texture.height:
        draw_value_row(
            details,
            "Size",
            f"{texture.width} × {texture.height}",
        )

    if texture.color_space:
        draw_value_row(details, "Color Space", texture.color_space)

    if texture.storage:
        draw_value_row(details, "Storage", texture.storage)

    draw_multiline_message(box, context, f"Node: {texture.node_path}", 96)

    if texture.filepath:
        draw_multiline_message(box, context, f"Path: {texture.filepath}", 96)


def draw_material_slot_result(layout, context, material, index, obj):
    box = layout.box()
    box.alert = material.status == "FAILED"

    if not draw_nested_result_header(
        box,
        context,
        "material_slot",
        index,
        f"{material.slot}: {material.name}",
        material.status,
    ):
        return

    draw_value_row(box, "Slot Link", material.link.title())
    draw_multiline_message(box, context, material.message, 80)

    for texture_index, texture in enumerate(material.textures):
        draw_texture_result(
            box,
            context,
            texture,
            f"{index}.{texture_index}",
            obj,
            material,
        )


def draw_material_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.material_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "material_results_expanded",
        "Last Material Check",
        len(results),
    )
    if not expanded:
        return

    box.label(text="Run the check again after changes")

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "material",
            index,
            entry.object_name,
            entry.status,
            entry.object_ref,
        )

        if not item_expanded:
            continue

        draw_multiline_message(item, context, entry.message)

        details = item.column(align=True)
        draw_value_row(details, "Materials", entry.material_count)
        draw_value_row(details, "Images", entry.image_count)
        draw_value_row(details, "Empty Slots", entry.empty_slots)

        for material_index, material in enumerate(entry.materials):
            draw_material_slot_result(
                item,
                context,
                material,
                f"{index}.{material_index}",
                entry.object_ref,
            )


def draw_material_slot_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.material_slot_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "material_slot_results_expanded",
        "Last Remove Empty Slots Results",
        len(results),
    )
    if not expanded:
        return

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "material_slots",
            index,
            entry.object_name,
            entry.status,
            entry.object_ref,
        )

        if not item_expanded:
            continue

        draw_multiline_message(item, context, entry.message)


class GEPREP_PT_materials(bpy.types.Panel):
    bl_idname = "GEPREP_PT_materials"
    bl_label = "Materials"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep

        check_box = layout.box()

        col = check_box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(settings, "material_max_texture_size")


        draw_action_button(
            check_box,
            "geprep.check_materials",
            "Check Materials",
            icon="VIEWZOOM",
        )

        draw_material_results(layout, settings, context)

        slots_box = layout.box()

        draw_action_button(
            slots_box,
            "geprep.remove_empty_material_slots",
            "Remove Empty Slots",
        )

        draw_material_slot_results(layout, settings, context)

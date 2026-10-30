import bpy

from ..helpers.objects import pointer_key, selected_meshes
from .common import (
    draw_action_button,
    draw_collapsible_box,
    draw_multiline_message,
    draw_result_focus_button,
    draw_result_item_header,
)


def draw_modifier_preview(layout, settings, context):
    ui = context.window_manager.geprep_ui

    objects = selected_meshes(context)

    if not objects:
        layout.label(
            text="Select one or more mesh objects",
            icon="INFO",
        )
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "modifier_preview_expanded",
        "Selected Meshes",
        len(objects),
    )

    if not expanded:
        return

    for obj in objects:
        entry = next(
            (
                entry
                for entry in ui.modifier_previews
                if entry.object_ref == obj
            ),
            None,
        )
        expanded = entry is not None and entry.expanded

        item = box.box()
        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"

        button = name_row.operator(
            "geprep.toggle_modifier_preview",
            text=f"{obj.name} ({len(obj.modifiers)})",
            icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
            emboss=False,
        )
        button.object_key = pointer_key(obj)

        focus_row = header.row(align=True)
        focus_row.alignment = "RIGHT"
        draw_result_focus_button(focus_row, context, obj)

        if not expanded:
            continue

        if not obj.modifiers:
            item.label(text="No modifiers")
            continue

        for modifier in obj.modifiers:
            row = item.row(align=True)
            visibility = row.row(align=True)
            visibility.enabled = (
                obj.is_editable
                and obj.override_library is None
            )
            visibility.prop(
                modifier,
                "show_viewport",
                text="",
                icon="HIDE_ON",
                icon_only=True,
                emboss=False,
                toggle=True,
            )

            row.separator(factor=0.4)

            row.label(text=modifier.name)

            type_row = row.row(align=True)
            type_row.alignment = "RIGHT"
            type_row.label(text=modifier.bl_rna.name)

            if not modifier.show_viewport:
                note = item.row()
                note.enabled = False
                note.label(text="Disabled in viewport, will be kept")


def draw_modifier_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.modifier_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "modifier_results_expanded",
        "Last Modifier Results",
        len(results),
    )
    if not expanded:
        return

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "modifiers",
            index,
            entry.object_name,
            entry.status,
            entry.object_ref,
        )

        if not item_expanded:
            continue

        if entry.status == "APPLIED":
            details = item.column(align=True)
            details.label(text=f"Applied modifiers: {entry.applied}")

            if entry.disabled:
                details.label(
                    text=f"Disabled modifiers kept: {entry.disabled}"
                )
            else:
                details.label(text="No disabled modifiers")

        draw_multiline_message(item, context, entry.message)


class GEPREP_PT_modifiers(bpy.types.Panel):
    bl_idname = "GEPREP_PT_modifiers"
    bl_label = "Modifiers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 2
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep

        draw_modifier_preview(layout, settings, context)

        draw_action_button(
            layout,
            "geprep.apply_modifiers",
            "Apply Modifiers",
            icon="CHECKMARK",
        )

        draw_modifier_results(layout, settings, context)

import bpy

from ..operations.checker import CHECKER_STYLES
from ..operations.uv import UV_FINDINGS
from ..operations.uv_orientation import MIRROR_ACTION, ORIENTATION_ACTIONS
from .common import (
    BUTTON_SCALE_Y,
    INPUT_SCALE_Y,
    draw_action_button,
    draw_collapsible_box,
    draw_finding_select_button,
    draw_multiline_message,
    draw_result_item_header,
    draw_value_row,
)


def draw_uv_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.uv_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "uv_results_expanded",
        "Last UV Check",
        len(results),
    )
    if not expanded:
        return

    box.label(
        text=(
            f"Texture: {settings.uv_checked_width} "
            f"× {settings.uv_checked_height}"
        )
    )
    box.label(
        text=(
            f"Target: {settings.uv_checked_target:g} px/m "
            f"(±{settings.uv_checked_tolerance:g}%)"
        )
    )

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "uv",
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

        details = item.column(align=True)

        values = [
            ("UV Map", entry.uv_name),
            (
                "Density (px/m)",
                f"{entry.density:.2f}"
                if entry.density_available
                else "Unavailable",
            ),
            ("Islands", str(entry.islands)),
            ("Tile Coverage", f"{entry.tile_coverage * 100:.1f}%"),
        ]

        if entry.density_available and entry.islands > 1:
            values.append((
                "Island Range",
                (
                    f"{entry.minimum_density:.2f}–"
                    f"{entry.maximum_density:.2f}"
                ),
            ))

        for label, value in values:
            draw_value_row(details, label, value)

        item.separator()
        item.label(text="Findings (faces)")

        findings = item.column(align=True)

        for key, label in UV_FINDINGS:
            count = getattr(entry, f"{key}_faces")
            row = draw_value_row(findings, label, count)

            if count:
                draw_finding_select_button(
                    row,
                    context,
                    entry.object_ref,
                    "geprep.select_uv_finding",
                    key,
                )


def draw_uv_density_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.uv_density_results

    if not results:
        return

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "uv_density_results_expanded",
        "Last Set Density Results",
        len(results),
    )
    if not expanded:
        return

    for index, entry in enumerate(results):
        item, item_expanded = draw_result_item_header(
            box,
            context,
            "uv_density",
            index,
            entry.object_name,
            entry.status,
            entry.object_ref,
        )

        if not item_expanded:
            continue

        draw_multiline_message(item, context, entry.message)


def draw_uv_orientation(layout, settings, context):
    ui = context.window_manager.geprep_ui

    box, expanded = draw_collapsible_box(
        layout,
        ui,
        "uv_orientation_expanded",
        "UV Orientation",
    )

    if not expanded:
        return

    in_edit_mode = context.mode == "EDIT_MESH"

    if in_edit_mode:
        box.label(text="Select faces. Whole islands are rotated")

    else:
        box.label(text="Enter Edit Mode and select faces", icon="INFO")

    col = box.column()
    col.scale_y = INPUT_SCALE_Y
    col.prop(settings, "uv_orientation_reference", text="Up Axis")
    col.prop(settings, "uv_orientation_tolerance")

    info_col = box.column(align=True)
    info_col.scale_y = 0.8
    info_col.label(text="Arrows point the cyan +U arrow")
    if settings.uv_orientation_reference == "AUTO":
        info_col.label(text="Up: world Z (walls), world Y (floors)")

    labels = {key: label for key, label, _ in ORIENTATION_ACTIONS}
    grid = box.column(align=True)
    grid.scale_y = BUTTON_SCALE_Y
    grid.enabled = in_edit_mode

    for actions in (
        (None, "UP", None),
        ("LEFT", "ALIGN", "RIGHT"),
        (None, "DOWN", None),
    ):
        row = grid.row(align=True)

        for action in actions:
            if action is None:
                row.label(text="")
                continue

            button = row.operator(
                "geprep.orient_uvs",
                text=labels[action],
            )
            button.action = action

    box.label(text="● points +U right and +V up")

    mirror_row = box.column()
    mirror_row.enabled = in_edit_mode
    draw_action_button(
        mirror_row,
        "geprep.orient_uvs",
        MIRROR_ACTION[1],
        action=MIRROR_ACTION[0],
    )


class GEPREP_PT_uv(bpy.types.Panel):
    bl_idname = "GEPREP_PT_uv"
    bl_label = "UV"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep
        ui = context.window_manager.geprep_ui
        active = context.view_layer.objects.active
        density_box, density_expanded = draw_collapsible_box(
            layout,
            ui,
            "uv_density_expanded",
            "Texel Density",
        )

        if density_expanded:
            col = density_box.column()
            col.scale_y = INPUT_SCALE_Y

            if active is not None and active.type == "MESH":
                col.prop_search(
                    settings,
                    "uv_map_name",
                    active.data,
                    "uv_layers",
                    text="UV Map",
                )
            else:
                col.prop(settings, "uv_map_name")

            col.prop(
                settings,
                "uv_texture_preset",
                text="Texture",
            )

            if settings.uv_texture_preset == "CUSTOM":
                row = col.row(align=True)
                row.prop(settings, "uv_texture_width")
                row.prop(settings, "uv_texture_height")

            col.prop(settings, "uv_density_preset")

            if settings.uv_density_preset == "CUSTOM":
                col.prop(settings, "uv_target_density")

            col.prop(settings, "uv_tolerance")

            col = density_box.column()
            col.scale_y = BUTTON_SCALE_Y
            row = col.row(align=True)
            row.operator(
                "geprep.check_uvs",
                text="Check UVs",
                icon="VIEWZOOM",
            )
            row.operator(
                "geprep.set_uv_density",
                text="Set Density",
            )

        draw_uv_results(layout, settings, context)
        draw_uv_density_results(layout, settings, context)

        draw_uv_orientation(layout, settings, context)

        checker_box = layout.box()
        checker_box.label(text="Checker Preview")
        col = checker_box.column()
        col.scale_y = BUTTON_SCALE_Y
        row = col.row(align=True)

        for style, label, _ in CHECKER_STYLES:
            button = row.operator("geprep.checker_preview", text=label)
            button.checker_style = style

        col.operator(
            "geprep.restore_checker",
            text="Remove Checker",
        )
        checker_box.label(text="Direction Checker: cyan +U, orange +V")

import textwrap

import bpy

from ..helpers.objects import pointer_key, selected_meshes
from ..operations.checker import CHECKER_STYLES
from ..operations.mesh import MESH_FINDINGS
from ..operations.uv import UV_FINDINGS
from ..operations.uv_orientation import MIRROR_ACTION, ORIENTATION_ACTIONS
from ..operators.mesh import MESH_FIX_ACTIONS
from ..operators.navigation import can_frame_object

BUTTON_SCALE_Y = 1.5
INPUT_SCALE_Y = 1.3

# Mesh fixes that take a distance, and the setting that holds it.
MESH_FIX_DISTANCE_PROPS = {
    "MERGE": "mesh_merge_distance",
    "DEGENERATE": "mesh_dissolve_distance",
}

RESULT_STATUS_ICONS = {
    "EXPORTED": "CHECKMARK",
    "CHANGED": "CHECKMARK",
    "PREPARED": "CHECKMARK",
    "RESTORED": "CHECKMARK",
    "APPLIED": "CHECKMARK",
    "PASSED": "CHECKMARK",
    "SKIPPED": "INFO",
    "INSPECT": "INFO",
    "FAILED": "ERROR",
    "INCOMPLETE": "ERROR",
}

RESULT_STATUS_LABELS = {
    "EXPORTED": "Exported",
    "CHANGED": "Changed",
    "PREPARED": "Prepared",
    "RESTORED": "Restored",
    "APPLIED": "Applied",
    "PASSED": "No Findings",
    "SKIPPED": "Skipped",
    "INSPECT": "Inspect",
    "FAILED": "Failed",
    "INCOMPLETE": "Recovery Failed",
}


def draw_collapsible_box(
    layout,
    ui,
    prop_name: str,
    title: str,
    count: int | None = None,
):
    """Draw a box whose header toggles a boolean on the UI settings."""
    box = layout.box()
    box.use_property_split = False
    expanded = getattr(ui, prop_name)
    box.prop(
        ui,
        prop_name,
        text=title if count is None else f"{title} ({count})",
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
    )
    return box, expanded


def draw_action_button(
    layout,
    idname: str,
    text: str,
    *,
    icon="NONE",
    **properties,
):
    """Draw one tall operator button and set the given operator properties."""
    col = layout.column()
    col.scale_y = BUTTON_SCALE_Y
    button = col.operator(idname, text=text, icon=icon)

    for name, value in properties.items():
        setattr(button, name, value)

    return button


def draw_value_row(layout, label: str, value):
    """Draw a label on the left and a right-aligned value."""
    row = layout.row(align=True)
    row.label(text=label)

    value_row = row.row(align=True)
    value_row.alignment = "RIGHT"
    value_row.label(text=str(value))

    return row


def draw_finding_select_button(row, context, target, idname: str, finding: str):
    """Add the 'select this finding' button to a finding row."""
    row.separator(factor=0.8)

    button_row = row.row(align=True)
    button_row.enabled = context.mode == "OBJECT" and target is not None

    button = button_row.operator(
        idname,
        text="",
        icon="RESTRICT_SELECT_OFF",
    )
    button.object_key = pointer_key(target)
    button.finding = finding


def draw_multiline_message(layout, context, message: str, width_offset: int = 48):
    """Draw wrapped multiline text adjusted to current viewport width."""
    if not message:
        return

    ui_scale = context.preferences.system.ui_scale
    available_width = context.region.width / ui_scale - width_offset
    characters_per_line = max(10, int(available_width / 7))

    message_column = layout.column(align=True)
    for paragraph in message.splitlines():
        for line in textwrap.wrap(paragraph, width=characters_per_line):
            message_column.label(text=line)


def draw_result_details_toggle(layout, context, section: str, index: int, text: str):
    ui = context.window_manager.geprep_ui
    key = f"{context.scene.session_uid}:{section}:{index}"

    entry = ui.result_foldouts.get(key)
    expanded = entry is not None and entry.expanded

    button = layout.operator(
        "geprep.toggle_result_details",
        text=text,
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
    )
    button.key = key

    return expanded


def draw_result_focus_button(layout, context, target):
    row = layout.row(align=True)
    row.enabled = can_frame_object(context, target)

    button = row.operator(
        "geprep.select_frame_object",
        text="",
        icon="VIEWZOOM",
    )
    button.object_key = pointer_key(target)


def draw_result_item_header(
    box,
    context,
    section: str,
    index: int,
    title: str,
    status: str,
    target_object=None,
    status_label: str | None = None,
):
    """Draw a standardized item card header for a single result entry."""
    item = box.box()
    item.use_property_split = False
    item.alert = status in {"FAILED", "INCOMPLETE"}

    header = item.row(align=True)

    name_row = header.row(align=True)
    name_row.alignment = "LEFT"
    expanded = draw_result_details_toggle(
        name_row,
        context,
        section,
        index,
        title,
    )

    status_row = header.row(align=True)
    status_row.alignment = "RIGHT"
    display_label = (
        status_label
        if status_label is not None
        else RESULT_STATUS_LABELS.get(status, status.capitalize())
    )
    status_row.label(
        text=display_label,
        icon=RESULT_STATUS_ICONS.get(status, "NONE"),
    )

    status_row.separator(factor=1.6)
    draw_result_focus_button(status_row, context, target_object)

    return item, expanded


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


def draw_nested_result_header(layout, context, section, index, title, status):
    """Draw a lighter foldout header for a result inside a result card."""
    row = layout.row(align=True)

    name_row = row.row(align=True)
    name_row.alignment = "LEFT"
    expanded = draw_result_details_toggle(
        name_row,
        context,
        section,
        index,
        title,
    )

    status_row = row.row(align=True)
    status_row.alignment = "RIGHT"
    status_row.label(
        text=RESULT_STATUS_LABELS.get(status, status.capitalize()),
        icon=RESULT_STATUS_ICONS.get(status, "NONE"),
    )

    return expanded


def draw_texture_result(layout, context, texture, index):
    box = layout.box()
    box.alert = texture.status == "FAILED"

    if not draw_nested_result_header(
        box,
        context,
        "material_texture",
        index,
        texture.name,
        texture.status,
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


def draw_material_slot_result(layout, context, material, index):
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


ORIGIN_GRID = (
    (("TL", "↖"), ("TC", "↑"), ("TR", "↗")),
    (("CL", "←"), ("C", "●"), ("CR", "→")),
    (("BL", "↙"), ("BC", "↓"), ("BR", "↘")),
)


class GEPREP_PT_origin(bpy.types.Panel):
    bl_idname = "GEPREP_PT_origin"
    bl_label = "Origin"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 6
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep

        box = layout.box()

        row = box.row(align=True)
        row.scale_y = INPUT_SCALE_Y
        row.prop(settings, "origin_depth", expand=True)

        grid = box.column(align=True)
        grid.scale_y = BUTTON_SCALE_Y

        for buttons in ORIGIN_GRID:
            row = grid.row(align=True)

            for position, arrow in buttons:
                button = row.operator("geprep.set_origin", text=arrow)
                button.position = position
                button.depth = settings.origin_depth

        draw_action_button(
            box,
            "geprep.set_origin",
            "Origin to 3D Cursor",
            icon="PIVOT_CURSOR",
            position="CURSOR",
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

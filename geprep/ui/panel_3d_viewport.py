import textwrap

import bpy

from ..operations.mesh import MESH_FINDINGS
from ..operations.uv import UV_FINDINGS
from ..operators.navigation import can_frame_object

BUTTON_SCALE_Y = 1.5
INPUT_SCALE_Y = 1.3

RESULT_STATUS_ICONS = {
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


def draw_results_box(layout, ui, prop_name: str, title: str, count: int):
    """Draw a standardized collapsable box header for result lists."""
    box = layout.box()
    box.use_property_split = False
    expanded = getattr(ui, prop_name)
    box.prop(
        ui,
        prop_name,
        text=f"{title} ({count})",
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
    )
    return box, expanded


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
    button.object_key = str(target.as_pointer()) if target is not None else ""


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

    box, expanded = draw_results_box(
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

        col = box.column()
        col.scale_y = BUTTON_SCALE_Y
        button = col.operator(
            "geprep.rename_objects",
            text="Set New Name",
        )
        button.action = "NEW"

        box = layout.box()
        col = box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(settings, "name_find", text="Replace")
        col.prop(settings, "name_replace", text="With")

        col = box.column()
        col.scale_y = BUTTON_SCALE_Y
        button = col.operator(
            "geprep.rename_objects",
            text="Find & Replace",
        )
        button.action = "REPLACE"

        box = layout.box()
        col = box.column()
        col.scale_y = BUTTON_SCALE_Y
        button = col.operator(
            "geprep.rename_objects",
            text="Remove Numeric Suffix",
        )
        button.action = "SUFFIX"

        draw_naming_results(layout, settings, context)


def draw_prepare_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.prepare_results

    if not results:
        return

    box, expanded = draw_results_box(
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

        col = prep_box.column()
        col.scale_y = BUTTON_SCALE_Y
        col.operator("geprep.prepare_copy", text="Prepare Copy")

        clean_box = layout.box()
        col = clean_box.column()
        col.scale_y = BUTTON_SCALE_Y
        col.operator(
            "geprep.remove_prepared_copies",
            text="Remove Prepared Copies",
        )

        draw_prepare_results(layout, settings, context)


def draw_modifier_preview(layout, settings, context):
    ui = context.window_manager.geprep_ui

    objects = sorted(
        (
            obj
            for obj in context.selected_objects
            if obj.type == "MESH"
        ),
        key=lambda obj: (obj.name.casefold(), obj.name),
    )

    if not objects:
        layout.label(
            text="Select one or more mesh objects",
            icon="INFO",
        )
        return

    box = layout.box()
    box.use_property_split = False
    box.prop(
        ui,
        "modifier_preview_expanded",
        text=f"Selected Meshes ({len(objects)})",
        icon=(
            "TRIA_DOWN"
            if ui.modifier_preview_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.modifier_preview_expanded:
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
        button.object_key = str(obj.as_pointer())

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

    box, expanded = draw_results_box(
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

        col = layout.column()
        col.scale_y = BUTTON_SCALE_Y
        col.operator(
            "geprep.apply_modifiers",
            text="Apply Modifiers",
            icon="CHECKMARK",
        )

        draw_modifier_results(layout, settings, context)


def draw_mesh_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.mesh_results

    if not results:
        return

    box, expanded = draw_results_box(
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
            row = totals.row(align=True)
            row.label(text=label)

            value = row.row(align=True)
            value.alignment = "RIGHT"
            value.label(text=str(count))

        item.separator()

        findings = item.column(align=True)

        for key, label, _ in MESH_FINDINGS:
            count = getattr(entry, key)

            row = findings.row(align=True)
            row.label(text=label)

            value = row.row(align=True)
            value.alignment = "RIGHT"
            value.label(text=str(count))

            if count:
                target = entry.object_ref

                row.separator(factor=0.8)

                button_row = row.row(align=True)
                button_row.enabled = (
                    context.mode == "OBJECT"
                    and target is not None
                )

                button = button_row.operator(
                    "geprep.select_mesh_finding",
                    text="",
                    icon="RESTRICT_SELECT_OFF",
                )
                button.object_key = (
                    str(target.as_pointer())
                    if target is not None
                    else ""
                )
                button.finding = key


def draw_mesh_fix_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.mesh_fix_results

    if not results:
        return

    box, expanded = draw_results_box(
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

        col = check_box.column()
        col.scale_y = BUTTON_SCALE_Y
        col.operator(
            "geprep.check_mesh",
            text="Check Mesh",
            icon="VIEWZOOM",
        )

        col = check_box.column()
        col.scale_y = INPUT_SCALE_Y
        col.prop(ui, "mesh_zoom_selection")
        col.prop(ui, "mesh_xray_selection")

        draw_mesh_results(layout, settings, context)

        fixes_main = layout.box()
        fixes_main.use_property_split = False
        fixes_main.prop(
            ui,
            "mesh_fixes_expanded",
            text="Mesh Fixes",
            icon="TRIA_DOWN" if ui.mesh_fixes_expanded else "TRIA_RIGHT",
            emboss=False,
        )

        if ui.mesh_fixes_expanded:
            box = fixes_main.box()
            col = box.column()
            col.scale_y = BUTTON_SCALE_Y
            button = col.operator(
                "geprep.mesh_fix",
                text="Remove Loose Geometry",
            )
            button.action = "LOOSE"

            box = fixes_main.box()
            col = box.column()
            col.scale_y = INPUT_SCALE_Y
            col.prop(settings, "mesh_merge_distance")
            col = box.column()
            col.scale_y = BUTTON_SCALE_Y
            button = col.operator(
                "geprep.mesh_fix",
                text="Merge by Distance",
            )
            button.action = "MERGE"

            box = fixes_main.box()
            col = box.column()
            col.scale_y = INPUT_SCALE_Y
            col.prop(settings, "mesh_dissolve_distance")
            col = box.column()
            col.scale_y = BUTTON_SCALE_Y
            button = col.operator(
                "geprep.mesh_fix",
                text="Dissolve Degenerate Geometry",
            )
            button.action = "DEGENERATE"

            box = fixes_main.box()
            col = box.column()
            col.scale_y = BUTTON_SCALE_Y
            button = col.operator(
                "geprep.mesh_fix",
                text="Recalculate Normals Outside",
            )
            button.action = "NORMALS"

            box = fixes_main.box()
            col = box.column()
            col.scale_y = BUTTON_SCALE_Y
            button = col.operator(
                "geprep.mesh_fix",
                text="Triangulate",
            )
            button.action = "TRIANGULATE"

        draw_mesh_fix_results(layout, settings, context)


def draw_uv_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.uv_results

    if not results:
        return

    box, expanded = draw_results_box(
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
            row = details.row(align=True)
            row.label(text=label)

            value_row = row.row(align=True)
            value_row.alignment = "RIGHT"
            value_row.label(text=value)

        item.separator()
        item.label(text="Findings (faces)")

        findings = item.column(align=True)

        for key, label in UV_FINDINGS:
            count = getattr(entry, f"{key}_faces")

            row = findings.row(align=True)
            row.label(text=label)

            value_row = row.row(align=True)
            value_row.alignment = "RIGHT"
            value_row.label(text=str(count))

            if count:
                target = entry.object_ref

                row.separator(factor=0.8)

                button_row = row.row(align=True)
                button_row.enabled = (
                    context.mode == "OBJECT"
                    and target is not None
                )

                button = button_row.operator(
                    "geprep.select_uv_finding",
                    text="",
                    icon="RESTRICT_SELECT_OFF",
                )
                button.object_key = (
                    str(target.as_pointer())
                    if target is not None
                    else ""
                )
                button.finding = key


def draw_uv_density_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.uv_density_results

    if not results:
        return

    box, expanded = draw_results_box(
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
        active = context.view_layer.objects.active

        density_box = layout.box()
        density_box.label(text="Texel Density")

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

        checker_box = layout.box()
        checker_box.label(text="Checker Preview")
        col = checker_box.column()
        col.scale_y = BUTTON_SCALE_Y
        row = col.row(align=True)
        row.operator(
            "geprep.checker_preview",
            text="Checker",
        )
        row.operator(
            "geprep.restore_checker",
            text="Remove Checker",
        )


class GEPREP_PT_materials(bpy.types.Panel):
    bl_idname = "GEPREP_PT_materials"
    bl_label = "Materials"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 5
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        pass


class GEPREP_PT_origin(bpy.types.Panel):
    bl_idname = "GEPREP_PT_origin"
    bl_label = "Origin"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 6
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        pass


class GEPREP_PT_export(bpy.types.Panel):
    bl_idname = "GEPREP_PT_export"
    bl_label = "Export"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 7
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        pass

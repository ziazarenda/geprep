import bpy
import textwrap

from ..operators.navigation import can_frame_object
from ..operations.mesh import MESH_FINDINGS
from ..operations.uv import UV_FINDINGS


def draw_result_details_toggle(layout, context, section, index, text):
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


def draw_naming_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.naming_results

    if not results:
        return

    box = layout.box()
    box.prop(
        ui,
        "naming_results_expanded",
        text=f"Last Naming Results ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if ui.naming_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.naming_results_expanded:
        return

    box.label(text="Results from the last naming attempt")

    icons = {
        "CHANGED": "CHECKMARK",
        "SKIPPED": "INFO",
        "FAILED": "ERROR",
        "INCOMPLETE": "ERROR",
    }

    labels = {
        "CHANGED": "Renamed",
        "SKIPPED": "Skipped",
        "FAILED": "Failed",
        "INCOMPLETE": "Recovery Failed",
    }

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status in {"FAILED", "INCOMPLETE"}

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        expanded = draw_result_details_toggle(
            name_row,
            context,
            "naming",
            index,
            entry.original_name,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        status_row.separator(factor=1.6)

        draw_result_focus_button(
            status_row,
            context,
            entry.object_ref,
        )

        if not expanded:
            continue

        item.label(text=f"Before: {entry.original_name}")
        item.label(text=f"After: {entry.resulting_name}")

        if entry.message:
            ui_scale = context.preferences.system.ui_scale
            available_width = context.region.width / ui_scale - 48
            characters_per_line = max(10, int(available_width / 7))

            message_column = item.column(align=True)

            for paragraph in entry.message.splitlines():
                for line in textwrap.wrap(
                    paragraph,
                    width=characters_per_line,
                ):
                    message_column.label(text=line)


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

        layout.label(text="Base Name")
        layout.prop(settings, "name_base", text="")

        button = layout.operator(
            "geprep.rename_objects",
            text="Set Base Name",
        )
        button.action = "BASE"

        layout.separator()

        layout.label(text="Find")
        layout.prop(settings, "name_find", text="")

        layout.label(text="Replace With")
        layout.prop(settings, "name_replace", text="")

        button = layout.operator(
            "geprep.rename_objects",
            text="Find & Replace",
        )
        button.action = "REPLACE"

        layout.separator()

        button = layout.operator(
            "geprep.rename_objects",
            text="Remove Numeric Suffix",
        )
        button.action = "SUFFIX"

        layout.separator()
        draw_naming_results(layout, settings, context)


def draw_prepare_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.prepare_results

    if not results:
        return

    box = layout.box()
    box.prop(
        ui,
        "prepare_results_expanded",
        text=f"Last Prepare Results ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if ui.prepare_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.prepare_results_expanded:
        return

    box.label(text="Results from the last Prepare action")

    icons = {
        "PREPARED": "CHECKMARK",
        "RESTORED": "CHECKMARK",
        "SKIPPED": "INFO",
        "FAILED": "ERROR",
        "INCOMPLETE": "ERROR",
    }

    labels = {
        "PREPARED": "Prepared",
        "RESTORED": "Restored",
        "SKIPPED": "Skipped",
        "FAILED": "Failed",
        "INCOMPLETE": "Recovery Failed",
    }

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status in {"FAILED", "INCOMPLETE"}

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        expanded = draw_result_details_toggle(
            name_row,
            context,
            "prepare",
            index,
            entry.original_name,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        target = (
            entry.duplicate
            if entry.duplicate is not None
            else entry.source
        )

        status_row.separator(factor=1.6)

        draw_result_focus_button(status_row, context, target)

        if not expanded:
            continue

        item.label(text=f"Original: {entry.original_name}")

        if entry.copy_name:
            item.label(text=f"Copy: {entry.copy_name}")

        if entry.message:
            ui_scale = context.preferences.system.ui_scale
            available_width = context.region.width / ui_scale - 48
            characters_per_line = max(10, int(available_width / 7))

            message_column = item.column(align=True)

            for paragraph in entry.message.splitlines():
                for line in textwrap.wrap(
                    paragraph,
                    width=characters_per_line,
                ):
                    message_column.label(text=line)


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

        layout.prop(settings, "prepare_include_children")
        layout.prop(settings, "prepare_use_sm_prefix")
        layout.prop(settings, "prepare_number_variants")
        layout.prop(settings, "prepare_duplicate_materials")
        layout.prop(settings, "prepare_apply_rotation_scale")

        layout.separator()

        row = layout.row()
        row.scale_y = 1.5
        row.operator("geprep.prepare_copy", text="Prepare Copy")

        row = layout.row()
        row.scale_y = 1.5
        row.operator(
            "geprep.remove_prepared_copies",
            text="Remove Prepared Copies",
        )

        layout.separator()
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

    box = layout.box()
    box.prop(
        ui,
        "modifier_results_expanded",
        text=f"Last Modifier Results ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if ui.modifier_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.modifier_results_expanded:
        return

    box.label(text="Results from the last Apply Modifiers action")

    icons = {
        "APPLIED": "CHECKMARK",
        "SKIPPED": "INFO",
        "FAILED": "ERROR",
        "INCOMPLETE": "ERROR",
    }

    labels = {
        "APPLIED": "Applied",
        "SKIPPED": "Skipped",
        "FAILED": "Failed",
        "INCOMPLETE": "Recovery Failed",
    }

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status in {"FAILED", "INCOMPLETE"}

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        expanded = draw_result_details_toggle(
            name_row,
            context,
            "modifiers",
            index,
            entry.object_name,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        status_row.separator(factor=1.6)
        draw_result_focus_button(
            status_row,
            context,
            entry.object_ref,
        )

        if not expanded:
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

        if entry.message:
            ui_scale = context.preferences.system.ui_scale
            available_width = context.region.width / ui_scale - 48
            characters_per_line = max(10, int(available_width / 7))

            message_column = item.column(align=True)

            for paragraph in entry.message.splitlines():
                for line in textwrap.wrap(
                    paragraph,
                    width=characters_per_line,
                ):
                    message_column.label(text=line)


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

        layout.operator(
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

    box = layout.box()
    box.prop(
        ui,
        "mesh_results_expanded",
        text=f"Last Mesh Check ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if ui.mesh_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.mesh_results_expanded:
        return

    box.label(
        text=f"Check distance: {settings.mesh_checked_distance:g} m"
    )

    icons = {
        "PASSED": "CHECKMARK",
        "INSPECT": "INFO",
        "FAILED": "ERROR",
    }

    labels = {
        "PASSED": "No Findings",
        "INSPECT": "Inspect",
        "FAILED": "Failed",
    }

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status == "FAILED"

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        expanded = draw_result_details_toggle(
            name_row,
            context,
            "mesh",
            index,
            entry.object_name,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        status_row.separator(factor=1.6)
        draw_result_focus_button(
            status_row,
            context,
            entry.object_ref,
        )

        if not expanded:
            continue

        if entry.message:
            ui_scale = context.preferences.system.ui_scale
            available_width = context.region.width / ui_scale - 48
            characters_per_line = max(10, int(available_width / 7))

            message_column = item.column(align=True)

            for paragraph in entry.message.splitlines():
                for line in textwrap.wrap(
                    paragraph,
                    width=characters_per_line,
                ):
                    message_column.label(text=line)

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

    box = layout.box()
    box.prop(
        ui,
        "mesh_fix_results_expanded",
        text=f"Last Mesh Fix Results ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if ui.mesh_fix_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.mesh_fix_results_expanded:
        return

    box.label(text=settings.mesh_fix_action)

    icons = {
        "CHANGED": "CHECKMARK",
        "SKIPPED": "INFO",
        "FAILED": "ERROR",
        "INCOMPLETE": "ERROR",
    }

    labels = {
        "CHANGED": "Changed",
        "SKIPPED": "Skipped",
        "FAILED": "Failed",
        "INCOMPLETE": "Recovery Failed",
    }

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status in {"FAILED", "INCOMPLETE"}

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        expanded = draw_result_details_toggle(
            name_row,
            context,
            "mesh_fixes",
            index,
            entry.object_name,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        status_row.separator(factor=1.6)
        draw_result_focus_button(
            status_row,
            context,
            entry.object_ref,
        )

        if not expanded:
            continue

        if entry.message:
            ui_scale = context.preferences.system.ui_scale
            available_width = context.region.width / ui_scale - 48
            characters_per_line = max(10, int(available_width / 7))

            message_column = item.column(align=True)

            for paragraph in entry.message.splitlines():
                for line in textwrap.wrap(
                    paragraph,
                    width=characters_per_line,
                ):
                    message_column.label(text=line)


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

        layout.prop(settings, "mesh_distance")

        layout.operator(
            "geprep.check_mesh",
            text="Check Mesh",
            icon="VIEWZOOM",
        )

        ui = context.window_manager.geprep_ui
        layout.prop(ui, "mesh_zoom_selection")
        layout.prop(ui, "mesh_xray_selection")

        draw_mesh_results(layout, settings, context)

        fixes = layout.box()
        fixes.label(text="Mesh Fixes")

        button = fixes.operator(
            "geprep.mesh_fix",
            text="Remove Loose Geometry",
        )
        button.action = "LOOSE"

        fixes.separator()
        fixes.prop(settings, "mesh_merge_distance")

        button = fixes.operator(
            "geprep.mesh_fix",
            text="Merge by Distance",
        )
        button.action = "MERGE"

        fixes.separator()

        button = fixes.operator(
            "geprep.mesh_fix",
            text="Recalculate Normals Outside",
        )
        button.action = "NORMALS"

        fixes.separator()

        button = fixes.operator(
            "geprep.mesh_fix",
            text="Triangulate",
        )
        button.action = "TRIANGULATE"

        fixes.separator()

        fixes.prop(settings, "mesh_dissolve_distance")

        button = fixes.operator(
            "geprep.mesh_fix",
            text="Dissolve Degenerate Geometry",
        )
        button.action = "DEGENERATE"

        draw_mesh_fix_results(fixes, settings, context)


def draw_uv_results(layout, settings, context):
    ui = context.window_manager.geprep_ui
    results = settings.uv_results

    if not results:
        return

    box = layout.box()
    box.prop(
        ui,
        "uv_results_expanded",
        text=f"Last UV Check ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if ui.uv_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.uv_results_expanded:
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

    icons = {
        "PASSED": "CHECKMARK",
        "INSPECT": "INFO",
        "FAILED": "ERROR",
    }

    labels = {
        "PASSED": "No Findings",
        "INSPECT": "Inspect",
        "FAILED": "Failed",
    }

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status == "FAILED"

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        expanded = draw_result_details_toggle(
            name_row,
            context,
            "uv",
            index,
            entry.object_name,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        status_row.separator(factor=1.6)
        draw_result_focus_button(
            status_row,
            context,
            entry.object_ref,
        )

        if not expanded:
            continue

        if entry.message:
            ui_scale = context.preferences.system.ui_scale
            available_width = context.region.width / ui_scale - 48
            characters_per_line = max(10, int(available_width / 7))

            message_column = item.column(align=True)

            for paragraph in entry.message.splitlines():
                for line in textwrap.wrap(
                    paragraph,
                    width=characters_per_line,
                ):
                    message_column.label(text=line)

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
                f"{entry.minimum_density:.2f}–"
                f"{entry.maximum_density:.2f}",
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

    box = layout.box()
    box.prop(
        ui,
        "uv_density_results_expanded",
        text=f"Last Set Density Results ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if ui.uv_density_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not ui.uv_density_results_expanded:
        return

    icons = {
        "CHANGED": "CHECKMARK",
        "SKIPPED": "INFO",
        "FAILED": "ERROR",
        "INCOMPLETE": "ERROR",
    }

    labels = {
        "CHANGED": "Changed",
        "SKIPPED": "Skipped",
        "FAILED": "Failed",
        "INCOMPLETE": "Recovery Failed",
    }

    for index, entry in enumerate(results):
        item = box.box()
        item.alert = entry.status in {"FAILED", "INCOMPLETE"}

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        expanded = draw_result_details_toggle(
            name_row,
            context,
            "uv_density",
            index,
            entry.object_name,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        status_row.separator(factor=1.6)
        draw_result_focus_button(
            status_row,
            context,
            entry.object_ref,
        )

        if not expanded:
            continue

        if entry.message:
            ui_scale = context.preferences.system.ui_scale
            available_width = context.region.width / ui_scale - 48
            characters_per_line = max(10, int(available_width / 7))

            message_column = item.column(align=True)

            for paragraph in entry.message.splitlines():
                for line in textwrap.wrap(
                    paragraph,
                    width=characters_per_line,
                ):
                    message_column.label(text=line)


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

        if active is not None and active.type == "MESH":
            layout.prop_search(
                settings,
                "uv_map_name",
                active.data,
                "uv_layers",
                text="UV Map",
            )
        else:
            layout.prop(settings, "uv_map_name")

        layout.prop(
            settings,
            "uv_texture_preset",
            text="Texture",
        )

        if settings.uv_texture_preset == "CUSTOM":
            row = layout.row(align=True)
            row.prop(settings, "uv_texture_width")
            row.prop(settings, "uv_texture_height")

        layout.prop(settings, "uv_density_preset")

        if settings.uv_density_preset == "CUSTOM":
            layout.prop(settings, "uv_target_density")

        layout.prop(settings, "uv_tolerance")

        row = layout.row(align=True)

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

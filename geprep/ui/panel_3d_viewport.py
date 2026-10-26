import bpy
import textwrap


def draw_naming_results(layout, settings, context):
    results = settings.naming_results

    if not results:
        return

    box = layout.box()
    box.prop(
        settings,
        "naming_results_expanded",
        text=f"Last Naming Results ({len(results)})",
        icon=(
            "TRIA_DOWN"
            if settings.naming_results_expanded
            else "TRIA_RIGHT"
        ),
        emboss=False,
    )

    if not settings.naming_results_expanded:
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

    for entry in results:
        item = box.box()
        item.alert = entry.status in {"FAILED", "INCOMPLETE"}

        header = item.row(align=True)

        name_row = header.row(align=True)
        name_row.alignment = "LEFT"
        name_row.prop(
            entry,
            "expanded",
            text=entry.original_name,
            icon="TRIA_DOWN" if entry.expanded else "TRIA_RIGHT",
            emboss=False,
        )

        status_row = header.row(align=True)
        status_row.alignment = "RIGHT"
        status_row.label(
            text=labels[entry.status],
            icon=icons[entry.status],
        )

        if not entry.expanded:
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


class GEPREP_PT_modifiers(bpy.types.Panel):
    bl_idname = "GEPREP_PT_modifiers"
    bl_label = "Modifiers"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 2
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        pass


class GEPREP_PT_mesh(bpy.types.Panel):
    bl_idname = "GEPREP_PT_mesh"
    bl_label = "Mesh"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 3
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        pass


class GEPREP_PT_uv(bpy.types.Panel):
    bl_idname = "GEPREP_PT_uv"
    bl_label = "UV"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 4
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        pass


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

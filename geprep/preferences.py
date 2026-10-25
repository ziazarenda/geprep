import bpy

from . import addon_updater_ops


class GEPREP_Preferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    export_directory: bpy.props.StringProperty(
        name="Default Export Folder",
        description="Default folder for exported assets",
        subtype="DIR_PATH",
        default="",
    )

    auto_check_update: bpy.props.BoolProperty(
        name="Auto-check for Updates",
        description="If enabled, auto-check for updates using an interval",
        default=False,
    )

    updater_interval_months: bpy.props.IntProperty(
        name="Months",
        description="Number of months between checking for updates",
        default=0,
        min=0,
    )

    updater_interval_days: bpy.props.IntProperty(
        name="Days",
        description="Number of days between checking for updates",
        default=7,
        min=0,
        max=31,
    )

    updater_interval_hours: bpy.props.IntProperty(
        name="Hours",
        description="Number of hours between checking for updates",
        default=0,
        min=0,
        max=23,
    )

    updater_interval_minutes: bpy.props.IntProperty(
        name="Minutes",
        description="Number of minutes between checking for updates",
        default=0,
        min=0,
        max=59,
    )

    def draw(self, context):
        layout = self.layout

        export_box = layout.box()
        export_box.label(text="Default Export Folder:")

        row = export_box.row(align=True)
        row.scale_y = 1.5
        row.scale_x = 1.5
        row.prop(self, "export_directory", text="")

        addon_updater_ops.update_settings_ui(self, context)

        row = layout.row()
        row.scale_y = 1.5
        button = row.operator(
            "wm.url_open",
            text="GitHub Repository",
        )
        button.url = addon_updater_ops.updater.website


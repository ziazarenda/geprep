import bpy


class GEPREP_PG_export_result(bpy.types.PropertyGroup):
    filename: bpy.props.StringProperty()
    filepath: bpy.props.StringProperty()
    status: bpy.props.EnumProperty(
        items=(
            ("EXPORTED", "Exported", ""),
            ("SKIPPED", "Skipped", ""),
            ("FAILED", "Failed", ""),
        ),
        default="FAILED",
    )
    message: bpy.props.StringProperty()

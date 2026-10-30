import bpy


class GEPREP_PG_naming_result(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)

    original_name: bpy.props.StringProperty()
    resulting_name: bpy.props.StringProperty()

    status: bpy.props.EnumProperty(
        items=(
            ("CHANGED", "Renamed", ""),
            ("SKIPPED", "Skipped", ""),
            ("FAILED", "Failed", ""),
            ("INCOMPLETE", "Recovery Failed", ""),
        ),
        default="SKIPPED",
    )

    message: bpy.props.StringProperty()

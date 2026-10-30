import bpy


class GEPREP_PG_modifier_preview(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    expanded: bpy.props.BoolProperty(default=False)


class GEPREP_PG_modifier_result(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    object_name: bpy.props.StringProperty()

    status: bpy.props.EnumProperty(
        items=(
            ("APPLIED", "Applied", ""),
            ("SKIPPED", "Skipped", ""),
            ("FAILED", "Failed", ""),
            ("INCOMPLETE", "Recovery Failed", ""),
        ),
        default="SKIPPED",
    )

    applied: bpy.props.IntProperty(default=0, min=0)
    disabled: bpy.props.IntProperty(default=0, min=0)
    message: bpy.props.StringProperty()

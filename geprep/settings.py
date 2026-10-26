import bpy


class GEPREP_PG_settings(bpy.types.PropertyGroup):
    name_base: bpy.props.StringProperty(
        name="Base Name",
        description="Base name for the selected objects",
    )

    name_find: bpy.props.StringProperty(
        name="Find",
        description="Case-sensitive text to find in object names",
    )

    name_replace: bpy.props.StringProperty(
        name="Replace With",
        description="Replacement text. Leave empty to remove matching text",
    )


def register():
    bpy.types.Scene.geprep = bpy.props.PointerProperty(
        type=GEPREP_PG_settings,
    )


def unregister():
    del bpy.types.Scene.geprep

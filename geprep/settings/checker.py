import bpy


class GEPREP_PG_checker_slot(bpy.types.PropertyGroup):
    link: bpy.props.EnumProperty(
        items=(
            ("DATA", "Data", "Material linked to the mesh"),
            ("OBJECT", "Object", "Material linked to the object"),
        ),
        default="DATA",
    )

    material: bpy.props.PointerProperty(
        type=bpy.types.Material,
    )


class GEPREP_PG_checker_record(bpy.types.PropertyGroup):
    """Checker state stored on the object so duplicates inherit it."""

    active: bpy.props.BoolProperty(
        default=False,
    )

    slots: bpy.props.CollectionProperty(
        type=GEPREP_PG_checker_slot,
    )

    checker: bpy.props.PointerProperty(
        type=bpy.types.Material,
    )

    temporary_slot: bpy.props.BoolProperty(
        default=False,
    )

    active_material_index: bpy.props.IntProperty(
        default=0,
        min=0,
    )

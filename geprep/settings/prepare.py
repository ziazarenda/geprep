import bpy


class GEPREP_PG_prepare_selection(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)


class GEPREP_PG_prepare_item(bpy.types.PropertyGroup):
    source: bpy.props.PointerProperty(type=bpy.types.Object)
    duplicate: bpy.props.PointerProperty(type=bpy.types.Object)

    original_hide_viewport: bpy.props.BoolProperty()
    original_hide_render: bpy.props.BoolProperty()
    original_hide_select: bpy.props.BoolProperty()
    original_hidden: bpy.props.BoolProperty()


class GEPREP_PG_prepare_batch(bpy.types.PropertyGroup):
    entries: bpy.props.CollectionProperty(type=GEPREP_PG_prepare_item)
    selection: bpy.props.CollectionProperty(type=GEPREP_PG_prepare_selection)
    original_active: bpy.props.PointerProperty(type=bpy.types.Object)
    view_layer: bpy.props.StringProperty()


class GEPREP_PG_prepare_result(bpy.types.PropertyGroup):
    source: bpy.props.PointerProperty(type=bpy.types.Object)
    duplicate: bpy.props.PointerProperty(type=bpy.types.Object)

    original_name: bpy.props.StringProperty()
    copy_name: bpy.props.StringProperty()

    status: bpy.props.EnumProperty(
        items=(
            ("PREPARED", "Prepared", ""),
            ("RESTORED", "Restored", ""),
            ("SKIPPED", "Skipped", ""),
            ("FAILED", "Failed", ""),
            ("INCOMPLETE", "Recovery Failed", ""),
        ),
        default="SKIPPED",
    )

    message: bpy.props.StringProperty()

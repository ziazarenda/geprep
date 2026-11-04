import bpy


class GEPREP_PG_texture_check(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    status: bpy.props.EnumProperty(
        items=(
            ("PASSED", "No Findings", ""),
            ("INSPECT", "Inspect", ""),
            ("FAILED", "Failed", ""),
        ),
        default="PASSED",
    )
    message: bpy.props.StringProperty()
    node_path: bpy.props.StringProperty()
    node_chain: bpy.props.StringProperty()
    width: bpy.props.IntProperty(min=0)
    height: bpy.props.IntProperty(min=0)
    color_space: bpy.props.StringProperty()
    storage: bpy.props.StringProperty()
    filepath: bpy.props.StringProperty()


class GEPREP_PG_material_check(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty()
    status: bpy.props.EnumProperty(
        items=(
            ("PASSED", "No Findings", ""),
            ("INSPECT", "Inspect", ""),
            ("FAILED", "Failed", ""),
        ),
        default="PASSED",
    )
    message: bpy.props.StringProperty()
    slot: bpy.props.IntProperty(min=0)
    link: bpy.props.StringProperty()
    textures: bpy.props.CollectionProperty(type=GEPREP_PG_texture_check)


class GEPREP_PG_material_result(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    object_name: bpy.props.StringProperty()
    status: bpy.props.EnumProperty(
        items=(
            ("PASSED", "No Findings", ""),
            ("INSPECT", "Inspect", ""),
            ("FAILED", "Failed", ""),
        ),
        default="PASSED",
    )
    message: bpy.props.StringProperty()
    material_count: bpy.props.IntProperty(min=0)
    image_count: bpy.props.IntProperty(min=0)
    empty_slots: bpy.props.IntProperty(min=0)
    materials: bpy.props.CollectionProperty(type=GEPREP_PG_material_check)


class GEPREP_PG_material_slot_result(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    object_name: bpy.props.StringProperty()
    status: bpy.props.EnumProperty(
        items=(
            ("CHANGED", "Changed", ""),
            ("SKIPPED", "Skipped", ""),
            ("FAILED", "Failed", ""),
            ("INCOMPLETE", "Recovery Failed", ""),
        ),
        default="SKIPPED",
    )
    message: bpy.props.StringProperty()

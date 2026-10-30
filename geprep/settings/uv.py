import bpy


class GEPREP_PG_uv_result(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    object_name: bpy.props.StringProperty()
    uv_name: bpy.props.StringProperty()

    status: bpy.props.EnumProperty(
        items=(
            ("PASSED", "No Findings", ""),
            ("INSPECT", "Inspect", ""),
            ("FAILED", "Failed", ""),
        ),
        default="FAILED",
    )

    message: bpy.props.StringProperty()

    density_available: bpy.props.BoolProperty()
    density: bpy.props.FloatProperty(min=0)
    minimum_density: bpy.props.FloatProperty(min=0)
    maximum_density: bpy.props.FloatProperty(min=0)

    islands: bpy.props.IntProperty(min=0)
    mismatched_islands: bpy.props.IntProperty(min=0)
    unmeasurable_islands: bpy.props.IntProperty(min=0)

    tile_coverage: bpy.props.FloatProperty(min=0.0, max=1.0)

    density_faces: bpy.props.IntProperty(min=0)
    outside_tile_faces: bpy.props.IntProperty(min=0)
    overlap_faces: bpy.props.IntProperty(min=0)
    collapsed_uv_faces: bpy.props.IntProperty(min=0)
    degenerate_mesh_faces: bpy.props.IntProperty(min=0)
    mirrored_faces: bpy.props.IntProperty(min=0)
    unmeasurable_faces: bpy.props.IntProperty(min=0)


class GEPREP_PG_uv_density_result(bpy.types.PropertyGroup):
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

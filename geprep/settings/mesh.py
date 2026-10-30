import bpy


class GEPREP_PG_mesh_result(bpy.types.PropertyGroup):
    object_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    object_name: bpy.props.StringProperty()

    status: bpy.props.EnumProperty(
        items=(
            ("PASSED", "No Findings", ""),
            ("INSPECT", "Inspect", ""),
            ("FAILED", "Failed", ""),
        ),
        default="FAILED",
    )

    message: bpy.props.StringProperty()

    vertices: bpy.props.IntProperty(min=0)
    edges: bpy.props.IntProperty(min=0)
    faces: bpy.props.IntProperty(min=0)
    triangles: bpy.props.IntProperty(min=0)

    ngons: bpy.props.IntProperty(min=0)
    loose_vertices: bpy.props.IntProperty(min=0)
    loose_edges: bpy.props.IntProperty(min=0)
    nearby_vertices: bpy.props.IntProperty(min=0)
    short_edges: bpy.props.IntProperty(min=0)
    small_faces: bpy.props.IntProperty(min=0)
    boundaries: bpy.props.IntProperty(min=0)
    nonmanifold_edges: bpy.props.IntProperty(min=0)
    nonmanifold_vertices: bpy.props.IntProperty(min=0)
    winding: bpy.props.IntProperty(min=0)


class GEPREP_PG_mesh_fix_result(bpy.types.PropertyGroup):
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

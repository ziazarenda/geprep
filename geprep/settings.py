import bpy


def update_uv_texture_preset(self, context):
    if self.uv_texture_preset == "CUSTOM":
        return

    size = int(self.uv_texture_preset)
    self.uv_texture_width = size
    self.uv_texture_height = size


def update_uv_density_preset(self, context):
    if self.uv_density_preset == "CUSTOM":
        return

    self.uv_target_density = float(self.uv_density_preset)


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


class GEPREP_PG_result_foldout(bpy.types.PropertyGroup):
    expanded: bpy.props.BoolProperty(default=False)


class GEPREP_PG_ui(bpy.types.PropertyGroup):
    naming_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    prepare_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    modifier_preview_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    modifier_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    modifier_previews: bpy.props.CollectionProperty(
        type=GEPREP_PG_modifier_preview,
        options={"SKIP_SAVE"},
    )

    mesh_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    mesh_fixes_expanded: bpy.props.BoolProperty(
        default=False,
        options={"SKIP_SAVE"},
    )

    mesh_fix_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    mesh_zoom_selection: bpy.props.BoolProperty(
        name="Zoom to Selection",
        description="Frame the geometry selected from a mesh finding",
        default=True,
        options={"SKIP_SAVE"},
    )

    mesh_xray_selection: bpy.props.BoolProperty(
        name="X-Ray on Select",
        description="Enable X-Ray when selecting a mesh finding",
        default=False,
        options={"SKIP_SAVE"},
    )

    uv_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    uv_density_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    result_foldouts: bpy.props.CollectionProperty(
        type=GEPREP_PG_result_foldout,
        options={"SKIP_SAVE"},
    )


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

    density_faces: bpy.props.IntProperty(min=0)
    outside_tile_faces: bpy.props.IntProperty(min=0)
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


class GEPREP_PG_settings(bpy.types.PropertyGroup):
    name_new: bpy.props.StringProperty(
        name="Name",
        description="New name for the selected objects",
    )

    name_find: bpy.props.StringProperty(
        name="Find",
        description="Case-sensitive text to find in object names",
    )

    name_replace: bpy.props.StringProperty(
        name="Replace With",
        description="Replacement text. Leave empty to remove matching text",
    )

    naming_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_naming_result,
        options={"SKIP_SAVE"},
    )

    # Prepare
    prepare_include_children: bpy.props.BoolProperty(
        name="Include Children",
        description="Include descendants of selected objects",
        default=True,
    )

    prepare_use_sm_prefix: bpy.props.BoolProperty(
        name="Add SM_ Prefix",
        description="Prefix prepared mesh names with SM_",
        default=True,
    )

    prepare_number_variants: bpy.props.BoolProperty(
        name="Number Variants",
        description="Use .001-style numbering for prepared copies",
        default=False,
    )

    prepare_duplicate_materials: bpy.props.BoolProperty(
        name="Duplicate Materials",
        description="Give copies independent materials. Texture images remain shared",
        default=False,
    )

    prepare_apply_rotation_scale: bpy.props.BoolProperty(
        name="Apply Rotation & Scale",
        description="Apply rotation and scale to copies. Check modifiers afterward",
        default=False,
    )

    prepare_batches: bpy.props.CollectionProperty(
        type=GEPREP_PG_prepare_batch,
    )

    prepare_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_prepare_result,
        options={"SKIP_SAVE"},
    )

    modifier_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_modifier_result,
        options={"SKIP_SAVE"},
    )

    # Mesh
    mesh_distance: bpy.props.FloatProperty(
        name="Check Distance (m)",
        description=(
            "Distance threshold in metres. "
            "Its square is used as the small-face area threshold"
        ),
        default=0.0001,
        min=0.000000001,
        precision=6,
    )

    mesh_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_mesh_result,
        options={"SKIP_SAVE"},
    )

    mesh_checked_distance: bpy.props.FloatProperty(
        options={"SKIP_SAVE"},
    )

    mesh_checked_units: bpy.props.FloatProperty(
        options={"SKIP_SAVE"},
    )

    mesh_fix_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_mesh_fix_result,
        options={"SKIP_SAVE"},
    )

    mesh_fix_action: bpy.props.StringProperty(
        options={"SKIP_SAVE"},
    )

    mesh_merge_distance: bpy.props.FloatProperty(
        name="Merge Distance (m)",
        description=(
            "Merge vertices within this distance in metres. "
            "May change faces, UVs, and seams"
        ),
        default=0.0001,
        min=0.000000001,
        precision=6,
    )

    mesh_dissolve_distance: bpy.props.FloatProperty(
        name="Dissolve Distance (m)",
        description=(
            "Distance threshold for dissolving degenerate geometry "
            "in metres. May change faces, UVs, and seams"
        ),
        default=0.0001,
        min=0.000000001,
        precision=6,
    )

    # UV
    uv_map_name: bpy.props.StringProperty(
        name="UV Map",
        description="Leave empty to use each object's active UV map",
    )

    uv_texture_preset: bpy.props.EnumProperty(
        name="Texture Size",
        description="Choose a square texture size or enter custom dimensions",
        items=(
            ("CUSTOM", "Custom", "Enter width and height manually"),
        ) + tuple(
            (
                str(size),
                f"{size} × {size}",
                f"Use a {size} × {size} texture",
            )
            for size in (256, 512, 1024, 2048, 4096, 8192)
        ),
        default="CUSTOM",
        update=update_uv_texture_preset,
    )

    uv_texture_width: bpy.props.IntProperty(
        name="Width",
        description="Texture width in pixels",
        default=2048,
        min=1,
    )

    uv_texture_height: bpy.props.IntProperty(
        name="Height",
        description="Texture height in pixels",
        default=2048,
        min=1,
    )

    uv_density_preset: bpy.props.EnumProperty(
        name="Density",
        description="Choose a target density or enter a custom value",
        items=(
            ("CUSTOM", "Custom", "Enter the target density manually"),
        ) + tuple(
            (
                str(density),
                f"{density} px/m",
                f"Target {density} pixels per metre",
            )
            for density in (128, 256, 512, 1024, 2048, 4096)
        ),
        default="CUSTOM",
        update=update_uv_density_preset,
    )

    uv_target_density: bpy.props.FloatProperty(
        name="Target (px/m)",
        description="Target texel density in pixels per metre",
        default=512,
        min=0.000001,
        precision=2,
    )

    uv_tolerance: bpy.props.FloatProperty(
        name="Tolerance (%)",
        description="Allowed percentage difference from the target density",
        default=10,
        min=0,
        max=100,
        precision=1,
    )

    uv_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_uv_result,
        options={"SKIP_SAVE"},
    )

    uv_checked_width: bpy.props.IntProperty(options={"SKIP_SAVE"})
    uv_checked_height: bpy.props.IntProperty(options={"SKIP_SAVE"})
    uv_checked_target: bpy.props.FloatProperty(options={"SKIP_SAVE"})
    uv_checked_tolerance: bpy.props.FloatProperty(options={"SKIP_SAVE"})
    uv_checked_units: bpy.props.FloatProperty(options={"SKIP_SAVE"})

    uv_density_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_uv_density_result,
        options={"SKIP_SAVE"},
    )


def register():
    bpy.types.Scene.geprep = bpy.props.PointerProperty(
        type=GEPREP_PG_settings,
    )
    bpy.types.Object.geprep_checker = bpy.props.PointerProperty(
        type=GEPREP_PG_checker_record,
    )
    bpy.types.WindowManager.geprep_ui = bpy.props.PointerProperty(
        type=GEPREP_PG_ui,
        options={"SKIP_SAVE"},
    )


def unregister():
    del bpy.types.WindowManager.geprep_ui
    del bpy.types.Object.geprep_checker
    del bpy.types.Scene.geprep

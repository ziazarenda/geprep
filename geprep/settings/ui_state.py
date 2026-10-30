import bpy

from .modifiers import GEPREP_PG_modifier_preview


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

    uv_density_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    uv_orientation_expanded: bpy.props.BoolProperty(
        default=False,
        options={"SKIP_SAVE"},
    )

    material_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    material_slot_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    export_results_expanded: bpy.props.BoolProperty(
        default=True,
        options={"SKIP_SAVE"},
    )

    result_foldouts: bpy.props.CollectionProperty(
        type=GEPREP_PG_result_foldout,
        options={"SKIP_SAVE"},
    )

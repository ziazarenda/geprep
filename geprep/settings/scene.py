import math

import bpy

from ..operations.export import EXPORT_MODES, default_glb_name
from ..operations.origin import ORIGIN_DEPTHS
from ..operations.uv_orientation import ORIENTATION_REFERENCES
from .export import GEPREP_PG_export_result
from .materials import (
    GEPREP_PG_material_result,
    GEPREP_PG_material_slot_result,
)
from .mesh import GEPREP_PG_mesh_fix_result, GEPREP_PG_mesh_result
from .modifiers import GEPREP_PG_modifier_result
from .naming import GEPREP_PG_naming_result
from .prepare import GEPREP_PG_prepare_batch, GEPREP_PG_prepare_result
from .uv import GEPREP_PG_uv_density_result, GEPREP_PG_uv_result


def update_uv_texture_preset(self, context):
    if self.uv_texture_preset == "CUSTOM":
        return

    size = int(self.uv_texture_preset)
    self.uv_texture_width = size
    self.uv_texture_height = size


def update_export_mode(self, context):
    if self.export_mode != "SEPARATE" and not self.export_name.strip():
        self.export_name = default_glb_name()


def update_uv_density_preset(self, context):
    if self.uv_density_preset == "CUSTOM":
        return

    self.uv_target_density = float(self.uv_density_preset)


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

    uv_orientation_reference: bpy.props.EnumProperty(
        name="Up Axis",
        description="Direction the Orient UVs arrows treat as up",
        items=ORIENTATION_REFERENCES,
        default="AUTO",
    )

    uv_orientation_tolerance: bpy.props.FloatProperty(
        name="Flatness Tolerance",
        description=(
            "How much an island may bend and still be rotated by its "
            "average direction. 0 accepts flat islands only"
        ),
        subtype="ANGLE",
        unit="ROTATION",
        default=0.0,
        min=0.0,
        max=math.radians(20.0),
        soft_max=math.radians(10.0),
        precision=1,
        step=10,
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

    # Materials
    material_max_texture_size: bpy.props.IntProperty(
        name="Max Texture Size (px)",
        description=(
            "Textures with a longer side than this are reported "
            "when materials are checked"
        ),
        default=4096,
        min=64,
        max=16384,
    )

    material_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_material_result,
        options={"SKIP_SAVE"},
    )

    material_slot_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_material_slot_result,
        options={"SKIP_SAVE"},
    )

    # Origin
    origin_depth: bpy.props.EnumProperty(
        name="Depth",
        description=(
            "Where the origin sits along the mesh's local Y axis. "
            "In the front view the front is the lowest Y"
        ),
        items=ORIGIN_DEPTHS,
        default="CENTER",
    )

    # Export
    export_folder: bpy.props.StringProperty(
        name="Folder",
        description=(
            "Folder for the GLB files. Start with // to use a path "
            "relative to the saved project"
        ),
        subtype="DIR_PATH",
    )

    export_mode: bpy.props.EnumProperty(
        name="Mode",
        items=EXPORT_MODES,
        default="SEPARATE",
        update=update_export_mode,
    )

    export_name: bpy.props.StringProperty(
        name="File Name",
        description="Name of the GLB file. Leave empty to use the project name",
    )

    export_materials: bpy.props.BoolProperty(
        name="Include Materials & Textures",
        description="Write materials and their images into the GLB",
        default=True,
    )

    export_tangents: bpy.props.BoolProperty(
        name="Include Tangents",
        description=(
            "Write tangents into the GLB. Most engines calculate their "
            "own, so this only makes the files bigger"
        ),
        default=False,
    )

    export_overwrite: bpy.props.BoolProperty(
        name="Overwrite Existing Files",
        description="Replace files that already exist in the folder",
        default=False,
    )

    export_results: bpy.props.CollectionProperty(
        type=GEPREP_PG_export_result,
        options={"SKIP_SAVE"},
    )

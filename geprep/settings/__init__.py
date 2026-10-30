"""Settings and property groups.

Every name is re-exported here, so `from .settings import X` still works.
"""

import bpy

from .checker import GEPREP_PG_checker_record, GEPREP_PG_checker_slot
from .export import GEPREP_PG_export_result
from .materials import (
    GEPREP_PG_material_check,
    GEPREP_PG_material_result,
    GEPREP_PG_material_slot_result,
    GEPREP_PG_texture_check,
)
from .mesh import GEPREP_PG_mesh_fix_result, GEPREP_PG_mesh_result
from .modifiers import GEPREP_PG_modifier_preview, GEPREP_PG_modifier_result
from .naming import GEPREP_PG_naming_result
from .prepare import (
    GEPREP_PG_prepare_batch,
    GEPREP_PG_prepare_item,
    GEPREP_PG_prepare_result,
    GEPREP_PG_prepare_selection,
)
from .scene import (
    GEPREP_PG_settings,
    update_export_mode,
    update_uv_density_preset,
    update_uv_texture_preset,
)
from .ui_state import GEPREP_PG_result_foldout, GEPREP_PG_ui
from .uv import GEPREP_PG_uv_density_result, GEPREP_PG_uv_result


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

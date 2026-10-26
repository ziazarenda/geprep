import bpy


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

    result_foldouts: bpy.props.CollectionProperty(
        type=GEPREP_PG_result_foldout,
        options={"SKIP_SAVE"},
    )


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


def register():
    bpy.types.Scene.geprep = bpy.props.PointerProperty(
        type=GEPREP_PG_settings,
    )
    bpy.types.WindowManager.geprep_ui = bpy.props.PointerProperty(
        type=GEPREP_PG_ui,
        options={"SKIP_SAVE"},
    )


def unregister():
    del bpy.types.WindowManager.geprep_ui
    del bpy.types.Scene.geprep

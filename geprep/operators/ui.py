import bpy


class GEPREP_OT_toggle_result_details(bpy.types.Operator):
    """Expand or collapse result details."""

    bl_idname = "geprep.toggle_result_details"
    bl_label = "Toggle Result Details"
    bl_options = {"INTERNAL"}

    key: bpy.props.StringProperty(
        options={"HIDDEN", "SKIP_SAVE"},
    )

    def execute(self, context):
        foldouts = context.window_manager.geprep_ui.result_foldouts
        entry = foldouts.get(self.key)

        if entry is None:
            entry = foldouts.add()
            entry.name = self.key

        entry.expanded = not entry.expanded

        if context.area is not None:
            context.area.tag_redraw()

        return {"FINISHED"}

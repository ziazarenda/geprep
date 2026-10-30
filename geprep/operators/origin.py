import bpy

from ..helpers.objects import has_selected_mesh, selected_meshes
from ..operations.origin import (
    ORIGIN_DEPTHS,
    ORIGIN_POSITIONS,
    all_origin_problems,
    move_mesh_origins,
    origin_targets,
    summarize_problems,
)


class GEPREP_OT_set_origin(bpy.types.Operator):
    """Move origins without moving the mesh geometry."""

    bl_idname = "geprep.set_origin"
    bl_label = "Set Origin"
    bl_options = {"REGISTER", "UNDO"}

    position: bpy.props.EnumProperty(
        name="Origin Position",
        items=ORIGIN_POSITIONS,
        default="C",
    )

    depth: bpy.props.EnumProperty(
        name="Depth",
        description="Where the origin sits along local Y. Not used for the 3D Cursor",
        items=ORIGIN_DEPTHS,
        default="CENTER",
    )

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and has_selected_mesh(context)

    @classmethod
    def description(cls, context, properties):
        for identifier, _, description in ORIGIN_POSITIONS:
            if identifier == properties.position:
                return description

        return "Move the origins of the selected meshes"

    def execute(self, context):
        objects = selected_meshes(context)

        problems = all_origin_problems(objects)

        if problems:
            self.report(
                {"ERROR"},
                "Can't set origins: " + summarize_problems(problems),
            )
            return {"CANCELLED"}

        try:
            context.view_layer.update()
            targets = origin_targets(
                objects,
                self.position,
                self.depth,
                context.scene.cursor.location.copy(),
            )
            move_mesh_origins(context, targets)
        except Exception as error:
            self.report({"ERROR"}, f"Couldn't set origins: {error}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Moved {len(objects)} mesh origin(s)")

        return {"FINISHED"}

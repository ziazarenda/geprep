import traceback

import bpy

from ..helpers.editors import show_shader_node
from ..helpers.node_chain import decode_chain, resolve_chain
from ..helpers.objects import find_object_by_key


def can_frame_object(context, obj):
    return (
        obj is not None
        and context.mode == "OBJECT"
        and context.area is not None
        and context.area.type == "VIEW_3D"
        and context.view_layer.objects.get(obj.name) == obj
        and not obj.hide_select
        and obj.visible_get(
            view_layer=context.view_layer,
            viewport=context.space_data,
        )
    )


class GEPREP_OT_select_frame_object(bpy.types.Operator):
    """Select this object and frame it in the current viewport."""

    bl_idname = "geprep.select_frame_object"
    bl_label = "Select & Frame Object"
    bl_options = {"INTERNAL"}

    object_key: bpy.props.StringProperty(
        options={"HIDDEN", "SKIP_SAVE"},
    )

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.area is not None
            and context.area.type == "VIEW_3D"
        )

    def execute(self, context):
        target = find_object_by_key(
            context.view_layer.objects,
            self.object_key,
        )

        if not can_frame_object(context, target):
            self.report({"WARNING"}, "This object is unavailable or cannot be selected")
            return {"CANCELLED"}

        region = next(
            (
                region
                for region in context.area.regions
                if region.type == "WINDOW"
            ),
            None,
        )

        if region is None:
            self.report({"WARNING"}, "Could not find the viewport window region")
            return {"CANCELLED"}

        original_selection = tuple(context.selected_objects)
        original_active = context.view_layer.objects.active

        try:
            with context.temp_override(region=region):
                if not bpy.ops.view3d.view_selected.poll():
                    self.report({"WARNING"}, "Cannot frame objects in this viewport")
                    return {"CANCELLED"}

                for obj in original_selection:
                    obj.select_set(False)

                target.select_set(True)
                context.view_layer.objects.active = target

                result = bpy.ops.view3d.view_selected(use_all_regions=False)

                if "FINISHED" not in result:
                    raise RuntimeError("Blender did not finish framing the object")

        except Exception as error:
            traceback.print_exc()

            for obj in tuple(context.selected_objects):
                obj.select_set(False)

            for obj in original_selection:
                obj.select_set(True)

            context.view_layer.objects.active = original_active
            self.report({"ERROR"}, f"Could not frame {target.name!r}: {error}")
            return {"CANCELLED"}

        return {"FINISHED"}


class GEPREP_OT_inspect_node(bpy.types.Operator):
    """Select the object and show this node in a Shader Editor."""

    bl_idname = "geprep.inspect_node"
    bl_label = "Show Node"
    bl_options = {"INTERNAL"}

    object_key: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    slot: bpy.props.IntProperty(options={"HIDDEN", "SKIP_SAVE"})
    material: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    node_chain: bpy.props.StringProperty(options={"HIDDEN", "SKIP_SAVE"})

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and context.area is not None

    def execute(self, context):
        obj = find_object_by_key(context.view_layer.objects, self.object_key)

        if (
            obj is None
            or obj.hide_select
            or not obj.visible_get(view_layer=context.view_layer)
        ):
            self.report({"WARNING"}, "This object is unavailable or cannot be selected")
            return {"CANCELLED"}

        slots = obj.material_slots
        material = slots[self.slot - 1].material if 0 < self.slot <= len(slots) else None
        names = decode_chain(self.node_chain)

        if (
            material is None
            or material.name != self.material
            or material.node_tree is None
            or names is None
        ):
            self.report({"WARNING"}, "The material changed. Run Check Materials again")
            return {"CANCELLED"}

        try:
            groups, node = resolve_chain(material.node_tree, names)
        except LookupError as error:
            self.report({"WARNING"}, f"{error}. Run Check Materials again")
            return {"CANCELLED"}

        try:
            for selected in tuple(context.selected_objects):
                selected.select_set(False)

            obj.select_set(True)
            context.view_layer.objects.active = obj
            obj.active_material_index = self.slot - 1

            show_shader_node(context, material, groups, node)
        except Exception as error:
            traceback.print_exc()
            self.report({"ERROR"}, f"Could not show the node: {error}")
            return {"CANCELLED"}

        return {"FINISHED"}

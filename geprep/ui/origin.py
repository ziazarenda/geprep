import bpy

from .common import BUTTON_SCALE_Y, INPUT_SCALE_Y, draw_action_button


ORIGIN_GRID = (
    (("TL", "↖"), ("TC", "↑"), ("TR", "↗")),
    (("CL", "←"), ("C", "●"), ("CR", "→")),
    (("BL", "↙"), ("BC", "↓"), ("BR", "↘")),
)


class GEPREP_PT_origin(bpy.types.Panel):
    bl_idname = "GEPREP_PT_origin"
    bl_label = "Origin"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"
    bl_order = 6
    bl_options = {"DEFAULT_CLOSED"}

    def draw(self, context):
        layout = self.layout
        settings = context.scene.geprep

        box = layout.box()

        row = box.row(align=True)
        row.scale_y = INPUT_SCALE_Y
        row.prop(settings, "origin_depth", expand=True)

        grid = box.column(align=True)
        grid.scale_y = BUTTON_SCALE_Y

        for buttons in ORIGIN_GRID:
            row = grid.row(align=True)

            for position, arrow in buttons:
                button = row.operator("geprep.set_origin", text=arrow)
                button.position = position
                button.depth = settings.origin_depth

        draw_action_button(
            box,
            "geprep.set_origin",
            "Origin to 3D Cursor",
            icon="PIVOT_CURSOR",
            position="CURSOR",
        )

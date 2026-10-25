import bpy


class GEPREP_PT_main(bpy.types.Panel):
    bl_idname = "GEPREP_PT_main"
    bl_label = "Asset Preparation"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "GEPrep"

    def draw(self, context):
        layout = self.layout
        layout.label(text="GEPrep")

# Register, unregister, and reload modules.

bl_info = {
    "name": "GEPrep",
    "author": "ziazarenda",
    "version": (1, 0, 3),
    "blender": (5, 2, 2),
    "location": "View3D > Sidebar > GEPrep",
    "description": "Prepare game environment assets",
    "category": "Object",
}


from . import auto_load
from . import addon_updater_ops

auto_load.init()


def register():
    addon_updater_ops.register(bl_info)
    auto_load.register()


def unregister():
    auto_load.unregister()
    addon_updater_ops.unregister()


# GEPrep specific: its three properties on Blender's own types must disappear
# when the add-on is disabled and come back when it is enabled again.
# (The kit's generic tests/blender/lifecycle.py covers errors and restore.)
import os

import addon_utils

import bpy

module = os.environ["ADDON_MODULE"]
checks = 0

PROPERTIES = (
    (bpy.types.Scene, "geprep"),
    (bpy.types.Object, "geprep_checker"),
    (bpy.types.WindowManager, "geprep_ui"),
)


def fail(error):
    raise error


def check(name, condition):
    global checks
    assert condition, name
    checks += 1
    print("PASS:", name)


def loaded():
    return bool(addon_utils.check(module)[1])


check("add-on is enabled at the start", loaded())

for round_number in range(1, 4):
    addon_utils.disable(module, default_set=False, handle_error=fail)
    check(f"round {round_number}: add-on is disabled", not loaded())
    for owner, name in PROPERTIES:
        check(f"round {round_number}: {owner.__name__}.{name} is removed", not hasattr(owner, name))
    check(f"round {round_number}: property groups are unregistered",
          not hasattr(bpy.types, "GEPREP_PG_settings"))

    addon_utils.enable(module, default_set=False, persistent=False, handle_error=fail)
    check(f"round {round_number}: add-on is enabled again", loaded())
    for owner, name in PROPERTIES:
        check(f"round {round_number}: {owner.__name__}.{name} is back", hasattr(owner, name))
    check(f"round {round_number}: scene settings are usable",
          bpy.context.scene.geprep is not None)
    check(f"round {round_number}: object checker record is usable",
          bpy.data.objects.new("lifecycle_probe", None).geprep_checker.active is False)
    bpy.data.objects.remove(bpy.data.objects["lifecycle_probe"])

print(f"\nALL {checks} CHECKS PASSED")

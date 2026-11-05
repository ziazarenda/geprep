import traceback

import bpy

from ..helpers.objects import has_selected_mesh, selected_meshes
from ..helpers.progress import with_progress
from ..operations.materials import (
    MaterialSlotCommitError,
    inspect_object_materials,
    remove_empty_material_slots,
)

CHECKER_ACTIVE_MESSAGE = (
    "A checker preview is active, so the real materials are hidden. "
    "Remove the checker and check again"
)


def run_material_check(context, objects):
    """Check the materials of `objects` and store the results.

    Returns (passed, inspect, failed) counts.
    """
    settings = context.scene.geprep
    results = settings.material_results
    results.clear()

    context.window_manager.geprep_ui.material_results_expanded = True

    image_cache = {}
    image_names = frozenset(image.name for image in bpy.data.images)

    for obj in with_progress(context, objects):
        entry = results.add()
        entry.object_ref = obj
        entry.object_name = obj.name

        if obj.geprep_checker.active:
            entry.status = "INSPECT"
            entry.message = CHECKER_ACTIVE_MESSAGE
            continue

        try:
            result = inspect_object_materials(
                obj,
                image_cache=image_cache,
                max_size=settings.material_max_texture_size,
                image_names=image_names,
            )
        except Exception as error:
            traceback.print_exc()
            entry.status = "FAILED"
            entry.message = f"Couldn't finish checking: {error}"
            continue

        entry.status = result["status"]
        entry.message = result["message"]
        entry.material_count = result["material_count"]
        entry.image_count = result["image_count"]
        entry.empty_slots = result["empty_slots"]

        for material in result["materials"]:
            item = entry.materials.add()
            item.name = material["name"]
            item.status = material["status"]
            item.message = material["message"]
            item.slot = material["slot"]
            item.link = material["link"]

            for texture in material["textures"]:
                image = item.textures.add()

                for key in (
                    "name",
                    "status",
                    "message",
                    "node_path",
                    "node_chain",
                    "width",
                    "height",
                    "color_space",
                    "storage",
                    "filepath",
                ):
                    setattr(image, key, texture[key])

    counts = {"PASSED": 0, "INSPECT": 0, "FAILED": 0}

    for entry in results:
        counts[entry.status] += 1

    return counts["PASSED"], counts["INSPECT"], counts["FAILED"]


class GEPREP_OT_check_materials(bpy.types.Operator):
    """Check material slots, image files, UV maps and color spaces. Make no changes. Findings may be intentional."""

    bl_idname = "geprep.check_materials"
    bl_label = "Check Materials"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and has_selected_mesh(context)
        )

    def execute(self, context):
        passed, inspect, failed = run_material_check(
            context,
            selected_meshes(context),
        )

        self.report(
            {"WARNING"} if failed else {"INFO"},
            f"Material check: {passed} without findings, "
            f"{inspect} to inspect, {failed} failed",
        )

        return {"FINISHED"}


class GEPREP_OT_remove_empty_material_slots(bpy.types.Operator):
    """Remove empty material slots that no faces use. Filled slots and slots used by faces are kept."""

    bl_idname = "geprep.remove_empty_material_slots"
    bl_label = "Remove Empty Slots"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == "OBJECT"
            and context.scene.is_editable
            and has_selected_mesh(context)
        )

    def execute(self, context):
        settings = context.scene.geprep
        objects = selected_meshes(context)
        results = settings.material_slot_results
        results.clear()

        context.window_manager.geprep_ui.material_slot_results_expanded = True

        removed = changed = skipped = failed = 0
        incomplete = False

        for obj in objects:
            entry = results.add()
            entry.object_ref = obj
            entry.object_name = obj.name

            if obj.geprep_checker.active:
                entry.status = "SKIPPED"
                entry.message = "Remove the checker before removing slots"
                skipped += 1
                continue

            try:
                count, entry.message = remove_empty_material_slots(obj)
            except MaterialSlotCommitError as error:
                traceback.print_exc()
                entry.status = "INCOMPLETE"
                entry.message = str(error)
                failed += 1
                incomplete = True
                self.report({"ERROR"}, f"'{obj.name}': {error}")
                break
            except Exception as error:
                traceback.print_exc()
                entry.status = "FAILED"
                entry.message = f"Couldn't remove empty slots: {error}"
                failed += 1
                continue

            entry.status = "CHANGED" if count else "SKIPPED"
            removed += count
            changed += bool(count)
            skipped += not count

        context.view_layer.update()

        if settings.material_results:
            run_material_check(context, objects)

        if incomplete:
            self.report(
                {"ERROR"},
                "Recovery failed. Use Undo before continuing",
            )
        else:
            self.report(
                {"WARNING"} if failed else {"INFO"},
                f"Removed {removed} empty slot(s) on {changed} mesh(es). "
                f"{failed} failed, {skipped} skipped",
            )

        return {"FINISHED"}

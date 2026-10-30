import os
import traceback

import bpy

from ..helpers.objects import has_selected_mesh, selected_meshes
from ..helpers.progress import with_progress
from ..operations.export import (
    ExportBlockedError,
    default_glb_name,
    export_glb_job,
    export_unit_scale,
    exporter_problem,
    format_size,
    gltf_export_arguments,
    material_failure_notes,
    plan_glb_files,
    summarize_notes,
)
from ..operations.materials import inspect_object_materials


def export_folder(settings):
    """Return the absolute export folder, creating it if needed.

    Raises ValueError with a message for the user when it cannot be used.
    """
    raw = settings.export_folder.strip()

    if not raw:
        raise ValueError("Choose an export folder")

    if raw.startswith("//") and not bpy.data.filepath:
        raise ValueError(
            "This folder path needs a saved project. "
            "Save the project or choose a full folder path"
        )

    try:
        folder = os.path.abspath(bpy.path.abspath(raw))
        os.makedirs(folder, exist_ok=True)
    except OSError as error:
        raise ValueError(f"Couldn't open export folder: {error}") from error

    return folder


def material_notes(settings, members):
    """Describe failed materials on the objects of one file."""
    image_cache = {}
    image_names = frozenset(image.name for image in bpy.data.images)
    notes = []

    for obj in members:
        inspection = inspect_object_materials(
            obj,
            image_cache=image_cache,
            max_size=settings.material_max_texture_size,
            image_names=image_names,
        )
        notes.extend(material_failure_notes(obj.name, inspection))

    return notes


def run_glb_export(context, objects, folder, unit_scale):
    """Export `objects` and store the results.

    Returns (exported, skipped, failed) counts.
    """
    settings = context.scene.geprep
    jobs = plan_glb_files(
        objects,
        folder,
        settings.export_mode,
        settings.export_name.strip() or default_glb_name(),
    )
    results = settings.export_results
    results.clear()
    context.window_manager.geprep_ui.export_results_expanded = True
    counts = {"EXPORTED": 0, "SKIPPED": 0, "FAILED": 0}

    for destination, members in with_progress(context, jobs, minimum=1):
        entry = results.add()
        entry.filename = os.path.basename(destination)
        entry.filepath = destination

        try:
            if (
                os.path.lexists(destination)
                and not settings.export_overwrite
            ):
                raise FileExistsError(
                    "File already exists. "
                    "Enable Overwrite Existing Files to replace it"
                )

            size = export_glb_job(
                context,
                members,
                destination,
                settings.export_mode,
                unit_scale,
                materials=settings.export_materials,
                tangents=settings.export_tangents,
                overwrite=settings.export_overwrite,
            )
            entry.status = "EXPORTED"
            message = (
                f"{len(members)} mesh(es), {format_size(size)}"
            )

            if settings.export_materials:
                try:
                    notes = material_notes(settings, members)
                except Exception:
                    # The file is already written; the notes are a bonus.
                    traceback.print_exc()
                    notes = []

                if notes:
                    message += (
                        "\nMaterial problems the file may not show:\n"
                        + summarize_notes(notes)
                    )

            entry.message = message

        except FileExistsError as error:
            entry.status = "SKIPPED"
            entry.message = str(error)

        except ExportBlockedError as error:
            # Expected and fixable: the message says what to do.
            entry.status = "FAILED"
            entry.message = str(error)

        except Exception as error:
            traceback.print_exc()
            entry.status = "FAILED"
            entry.message = str(error)

        counts[entry.status] += 1

    return counts["EXPORTED"], counts["SKIPPED"], counts["FAILED"]


class GEPREP_OT_export_glb(bpy.types.Operator):
    """Export the selected meshes as GLB files. Scene unit scale is applied, Y is up."""

    bl_idname = "geprep.export_glb"
    bl_label = "Export GLB"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and has_selected_mesh(context)

    def execute(self, context):
        settings = context.scene.geprep
        objects = selected_meshes(context)

        with_checker = [
            obj.name for obj in objects if obj.geprep_checker.active
        ]

        if with_checker:
            self.report(
                {"WARNING"},
                "Remove the checker before exporting: "
                + ", ".join(with_checker),
            )
            return {"CANCELLED"}

        problem = exporter_problem(
            gltf_export_arguments(
                "",
                materials=settings.export_materials,
                tangents=settings.export_tangents,
            )
        )

        if problem:
            self.report({"ERROR"}, problem)
            return {"CANCELLED"}

        try:
            unit_scale = export_unit_scale(context.scene)
            folder = export_folder(settings)
        except ValueError as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

        context.view_layer.update()
        exported, skipped, failed = run_glb_export(
            context,
            objects,
            folder,
            unit_scale,
        )

        self.report(
            {"WARNING"} if failed else {"INFO"},
            f"GLB export: {exported} exported, {skipped} skipped, "
            f"{failed} failed",
        )

        return {"FINISHED"}

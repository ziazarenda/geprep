"""Runs ONE Blender test script inside Blender. Started by build.py.

    blender --python _run_in_blender.py -- <test file>

Settings come from environment variables set by build.py:
    GEPREP_RESULT  where to write the result (JSON)
    GEPREP_ADDON   the add-on folder that must be the one that is tested

The result file is how build.py learns the outcome, so a crash or a
timeout can never look like a pass.
"""
import contextlib
import io
import json
import os
import sys
import traceback

import bpy

# These tests switch the window's scene, so they need a real window.
NEEDS_WINDOW = {"export.py", "origin.py"}


class Tee(io.StringIO):
    """Keep a copy of the output and still print it."""

    def write(self, text):
        sys.__stdout__.write(text)
        return super().write(text)


def run_test(test_path, expected_addon, result):
    import addon_utils

    module = addon_utils.enable("geprep", default_set=False, persistent=False)

    if module is None:
        raise RuntimeError("The add-on could not be enabled. See the error above")

    loaded = os.path.realpath(module.__file__)
    expected = os.path.realpath(expected_addon)

    if not loaded.startswith(expected + os.sep):
        raise RuntimeError(
            f"Tested the wrong copy of the add-on: {loaded} (expected under {expected})"
        )

    name = os.path.basename(test_path)

    if name in NEEDS_WINDOW and bpy.context.window is None:
        result["status"] = "skipped"
        result["error"] = "Needs a Blender window (run without --headless)"
        return

    with open(test_path, encoding="utf-8") as handle:
        source = handle.read()

    output = Tee()

    with contextlib.redirect_stdout(output):
        exec(compile(source, test_path, "exec"), {"__name__": "__main__"})

    lines = output.getvalue().splitlines()
    result["passes"] = sum(line.startswith("PASS:") for line in lines)
    finished = any(line.startswith("ALL ") and line.endswith("PASSED") for line in lines)

    if not result["passes"] or not finished:
        raise RuntimeError("The test ended without its 'ALL ... PASSED' line")

    result["status"] = "passed"


def main():
    arguments = sys.argv[sys.argv.index("--") + 1:]
    test_path = arguments[0]
    result_path = os.environ["GEPREP_RESULT"]
    result = {"test": os.path.basename(test_path), "status": "failed",
              "passes": 0, "error": ""}

    try:
        run_test(test_path, os.environ["GEPREP_ADDON"], result)
    except BaseException:
        result["status"] = "failed"
        result["error"] = traceback.format_exc()[-3000:]
        traceback.print_exc()
    finally:
        with open(result_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle)

        if not bpy.app.background:
            bpy.ops.wm.quit_blender()


if bpy.app.background:
    main()
else:
    # Let the window finish opening first.
    bpy.app.timers.register(main, first_interval=1.0)

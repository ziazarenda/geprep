# GEPrep tests

## `plain/` – no Blender needed
Logic tests that run with a normal Python (numpy required). They load the
add-on's modules with small stand-ins for `bpy` and `mathutils`.

    python tests/plain/_run_all.py         # all of them
    python tests/plain/origin_logic.py     # one

## `blender/` – run inside Blender
Each file is one script wrapped in `exec("""...""")`. Install the add-on
first, restart Blender after copying new files, then:

1. Open Blender's **Scripting** workspace.
2. Paste the file's whole content into the **Python console** and press Enter.
3. Read the `PASS:` lines. The last line says "ALL ... PASSED"; an
   `AssertionError` names the check that failed.

Every script creates temporary objects with a random name prefix and removes
them afterwards.

| Script | What it covers |
| --- | --- |
| `uv_findings.py` | UV findings: overlap, coverage, mirrored islands |
| `checker.py` | Checker preview material, density preset, restore |
| `materials.py` | Material check, node groups, Mix/Separate colour tracing, slot removal |
| `export.py` | Real GLB export: modes, names, unit scale, overwrite, tangents |
| `origin.py` | Set Origin: all positions and depths, children, shape keys, refusals |

Manual checks no script covers: Ctrl+Z after Remove Empty Slots and after
Set Origin, the arrow glyphs in the Origin panel, and the progress
percentage on a 20+ object selection.

Files starting with `_` (`plain/_run_all.py`, `blender/_run_in_blender.py`) are helpers, not tests. `build.py` and the runners skip them.

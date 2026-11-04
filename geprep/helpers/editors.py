"""Find an editor area (or open one in a new window) and frame its view.

Blender cannot move the mouse focus, so "go there" means: make sure a
suitable editor is visible and set up. Existing areas are reused; if none
fits, a new window is opened, so the user's own layout is never changed.
"""

import traceback

import bpy


def find_area(context, area_type, accept=None):
    """Return (window, area) of the first matching editor, current window first."""
    current = context.window
    windows = sorted(
        context.window_manager.windows,
        key=lambda window: window != current,
    )

    for window in windows:
        for area in window.screen.areas:
            if area.type != area_type:
                continue

            if accept is None or accept(area.spaces.active):
                return window, area

    return None, None


def open_new_window(context, area_type):
    """Open a new window whose only area is `area_type`. Returns (window, area)."""
    manager = context.window_manager
    known = {window.as_pointer() for window in manager.windows}

    bpy.ops.wm.window_new()

    window = next(
        (
            window
            for window in manager.windows
            if window.as_pointer() not in known
        ),
        None,
    )

    if window is None:
        raise RuntimeError("Blender did not open a new window")

    area = max(window.screen.areas, key=lambda area: area.width * area.height)
    area.type = area_type

    return window, area


def run_when_ready(window, area, callback, *, tries=40, interval=0.05):
    """Run `callback()` inside the area once it has been drawn.

    A new or re-typed area has no usable size until Blender redraws it,
    and view operators need that size. Does nothing when the area closes.
    """
    window_key = window.as_pointer()
    area_key = area.as_pointer()
    left = [tries]

    def step():
        manager = bpy.context.window_manager
        win = next(
            (w for w in manager.windows if w.as_pointer() == window_key),
            None,
        )
        found = None if win is None else next(
            (a for a in win.screen.areas if a.as_pointer() == area_key),
            None,
        )

        if found is None:
            return None

        region = next((r for r in found.regions if r.type == "WINDOW"), None)

        if region is None or region.width <= 1 or region.height <= 1:
            left[0] -= 1
            return interval if left[0] > 0 else None

        try:
            with bpy.context.temp_override(
                window=win,
                area=found,
                region=region,
                space_data=found.spaces.active,
            ):
                callback()
        except Exception:
            traceback.print_exc()

        return None

    bpy.app.timers.register(step, first_interval=interval)


def show_uv_editor(context, *, frame_selected=False):
    """Show an Image Editor in UV mode and frame the 0-1 tile.

    Reuses an Image Editor that is already in UV mode, then any Image
    Editor, then opens a new window. With `frame_selected` it frames the
    selected UVs first (for faces outside the tile) and falls back to the tile.
    """
    window, area = find_area(
        context,
        "IMAGE_EDITOR",
        lambda space: space.ui_mode == "UV",
    )

    if area is None:
        window, area = find_area(context, "IMAGE_EDITOR")

    if area is None:
        window, area = open_new_window(context, "IMAGE_EDITOR")

    space = area.spaces.active

    try:
        space.ui_mode = "UV"
    except (AttributeError, TypeError):
        space.mode = "UV"

    def frame():
        if frame_selected:
            try:
                if "FINISHED" in bpy.ops.image.view_selected():
                    return
            except RuntimeError:
                pass

        bpy.ops.image.view_all(fit_view=True)

    run_when_ready(window, area, frame)


def show_shader_node(context, material, groups, node):
    """Show `node` of `material` in a Shader Editor, entering its groups, and frame it."""
    window, area = find_area(
        context,
        "NODE_EDITOR",
        lambda space: space.tree_type == "ShaderNodeTree" and not space.pin,
    )

    if area is None:
        window, area = open_new_window(context, "NODE_EDITOR")
        area.spaces.active.tree_type = "ShaderNodeTree"

    space = area.spaces.active
    space.shader_type = "OBJECT"

    space.path.clear()
    space.path.append(material.node_tree)

    for group in groups:
        space.path.append(group.node_tree, node=group)

    tree = groups[-1].node_tree if groups else material.node_tree

    for other in tree.nodes:
        other.select = False

    node.select = True
    tree.nodes.active = node

    run_when_ready(window, area, bpy.ops.node.view_selected)

import textwrap

from ..helpers.objects import pointer_key
from ..operators.navigation import can_frame_object


BUTTON_SCALE_Y = 1.5

INPUT_SCALE_Y = 1.3

RESULT_STATUS_ICONS = {
    "EXPORTED": "CHECKMARK",
    "CHANGED": "CHECKMARK",
    "PREPARED": "CHECKMARK",
    "RESTORED": "CHECKMARK",
    "APPLIED": "CHECKMARK",
    "PASSED": "CHECKMARK",
    "SKIPPED": "INFO",
    "INSPECT": "INFO",
    "FAILED": "ERROR",
    "INCOMPLETE": "ERROR",
}

RESULT_STATUS_LABELS = {
    "EXPORTED": "Exported",
    "CHANGED": "Changed",
    "PREPARED": "Prepared",
    "RESTORED": "Restored",
    "APPLIED": "Applied",
    "PASSED": "No Findings",
    "SKIPPED": "Skipped",
    "INSPECT": "Inspect",
    "FAILED": "Failed",
    "INCOMPLETE": "Recovery Failed",
}


def draw_collapsible_box(
    layout,
    ui,
    prop_name: str,
    title: str,
    count: int | None = None,
):
    """Draw a box whose header toggles a boolean on the UI settings."""
    box = layout.box()
    box.use_property_split = False
    expanded = getattr(ui, prop_name)
    box.prop(
        ui,
        prop_name,
        text=title if count is None else f"{title} ({count})",
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
    )
    return box, expanded


def draw_action_button(
    layout,
    idname: str,
    text: str,
    *,
    icon="NONE",
    **properties,
):
    """Draw one tall operator button and set the given operator properties."""
    col = layout.column()
    col.scale_y = BUTTON_SCALE_Y
    button = col.operator(idname, text=text, icon=icon)

    for name, value in properties.items():
        setattr(button, name, value)

    return button


def draw_value_row(layout, label: str, value):
    """Draw a label on the left and a right-aligned value."""
    row = layout.row(align=True)
    row.label(text=label)

    value_row = row.row(align=True)
    value_row.alignment = "RIGHT"
    value_row.label(text=str(value))

    return row


def draw_finding_select_button(row, context, target, idname: str, finding: str):
    """Add the 'select this finding' button to a finding row."""
    row.separator(factor=0.8)

    button_row = row.row(align=True)
    button_row.enabled = context.mode == "OBJECT" and target is not None

    button = button_row.operator(
        idname,
        text="",
        icon="RESTRICT_SELECT_OFF",
    )
    button.object_key = pointer_key(target)
    button.finding = finding


def draw_multiline_message(layout, context, message: str, width_offset: int = 48):
    """Draw wrapped multiline text adjusted to current viewport width."""
    if not message:
        return

    ui_scale = context.preferences.system.ui_scale
    available_width = context.region.width / ui_scale - width_offset
    characters_per_line = max(10, int(available_width / 7))

    message_column = layout.column(align=True)
    for paragraph in message.splitlines():
        for line in textwrap.wrap(paragraph, width=characters_per_line):
            message_column.label(text=line)


def draw_result_details_toggle(layout, context, section: str, index: int, text: str):
    ui = context.window_manager.geprep_ui
    key = f"{context.scene.session_uid}:{section}:{index}"

    entry = ui.result_foldouts.get(key)
    expanded = entry is not None and entry.expanded

    button = layout.operator(
        "geprep.toggle_result_details",
        text=text,
        icon="TRIA_DOWN" if expanded else "TRIA_RIGHT",
        emboss=False,
    )
    button.key = key

    return expanded


def draw_result_focus_button(layout, context, target):
    row = layout.row(align=True)
    row.enabled = can_frame_object(context, target)

    button = row.operator(
        "geprep.select_frame_object",
        text="",
        icon="VIEWZOOM",
    )
    button.object_key = pointer_key(target)


def draw_result_item_header(
    box,
    context,
    section: str,
    index: int,
    title: str,
    status: str,
    target_object=None,
    status_label: str | None = None,
):
    """Draw a standardized item card header for a single result entry."""
    item = box.box()
    item.use_property_split = False
    item.alert = status in {"FAILED", "INCOMPLETE"}

    header = item.row(align=True)

    name_row = header.row(align=True)
    name_row.alignment = "LEFT"
    expanded = draw_result_details_toggle(
        name_row,
        context,
        section,
        index,
        title,
    )

    status_row = header.row(align=True)
    status_row.alignment = "RIGHT"
    display_label = (
        status_label
        if status_label is not None
        else RESULT_STATUS_LABELS.get(status, status.capitalize())
    )
    status_row.label(
        text=display_label,
        icon=RESULT_STATUS_ICONS.get(status, "NONE"),
    )

    status_row.separator(factor=1.6)
    draw_result_focus_button(status_row, context, target_object)

    return item, expanded


def draw_nested_result_header(
    layout, context, section, index, title, status, extra=None
):
    """Draw a lighter foldout header for a result inside a result card."""
    row = layout.row(align=True)

    name_row = row.row(align=True)
    name_row.alignment = "LEFT"
    expanded = draw_result_details_toggle(
        name_row,
        context,
        section,
        index,
        title,
    )

    status_row = row.row(align=True)
    status_row.alignment = "RIGHT"
    status_row.label(
        text=RESULT_STATUS_LABELS.get(status, status.capitalize()),
        icon=RESULT_STATUS_ICONS.get(status, "NONE"),
    )

    if extra is not None:
        extra(status_row)

    return expanded

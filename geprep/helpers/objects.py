"""Small object helpers shared by operators and the panel."""


def selected_meshes(context):
    """Return the selected mesh objects, sorted by name."""
    return sorted(
        (
            obj
            for obj in context.selected_objects
            if obj.type == "MESH"
        ),
        key=lambda obj: (obj.name.casefold(), obj.name),
    )


def has_selected_mesh(context):
    """Return whether at least one selected object is a mesh."""
    return any(obj.type == "MESH" for obj in context.selected_objects)


def pointer_key(obj):
    """Identify an object in a button property; '' when there is none.

    The key is only valid for the current UI redraw. Look the object up
    again with find_object_by_key() when the button is pressed.
    """
    return str(obj.as_pointer()) if obj is not None else ""


def find_object_by_key(objects, key):
    """Return the object from `objects` that matches pointer_key()."""
    return next(
        (obj for obj in objects if pointer_key(obj) == key),
        None,
    )


def restore_material_links(obj, slots, active_index=None):
    """Put saved material slot links back on an object.

    `slots` is a list of (link, material) pairs, one per slot. Slots linked
    to the object get their object-level material back. Raises RuntimeError
    when the object has a different number of slots than `slots`.
    """
    if len(obj.material_slots) != len(slots):
        raise RuntimeError(
            "Material slot count does not match the original"
        )

    for slot, (link, material) in zip(obj.material_slots, slots):
        slot.link = link

        if link == "OBJECT":
            slot.material = material

    if active_index is not None:
        obj.active_material_index = active_index


def has_animation(data):
    """Check an object or data-block for an action, drivers, or NLA tracks."""
    animation = getattr(data, "animation_data", None)

    return animation is not None and (
        animation.action is not None
        or bool(animation.drivers)
        or bool(animation.nla_tracks)
    )

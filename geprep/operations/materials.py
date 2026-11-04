"""Check materials and texture images. Remove unused empty material slots.

Checks only read data. They return plain dicts that the operators copy
into the result properties, the same way inspect_uv_mesh() does.
"""

import os
import re
from array import array

import bpy

from ..helpers.node_chain import encode_chain
from ..helpers.objects import restore_material_links

STATUS_PRIORITY = {"FAILED": 0, "INSPECT": 1, "PASSED": 2}

# Image inputs that hold colors. Other shader inputs hold data.
COLOR_USES = frozenset({"Base Color", "Emission Color"})

DEFAULT_MAX_TEXTURE_SIZE = 4096

_DUPLICATE_NAME = re.compile(r"(.+)\.\d{3}")

_UNSUPPORTED_IMAGE_SOURCES = {
    "TILED": "UDIM image. Tiles are not fully checked. Check them manually",
    "SEQUENCE": (
        "Image sequence. Frames are not fully checked. "
        "Check them manually"
    ),
    "MOVIE": "Movie texture. Check its frames and GLB export manually",
    "VIEWER": (
        "Render or viewer image. Check the image and GLB export manually"
    ),
}


def worst_status(statuses):
    """Return the most serious status, or PASSED when there are none."""
    return min(
        statuses,
        key=STATUS_PRIORITY.__getitem__,
        default="PASSED",
    )


def combine_issues(issues):
    """Turn a list of (status, message) pairs into one status and text."""
    return (
        worst_status(status for status, _ in issues),
        "\n".join(message for _, message in issues if message),
    )


def material_nodes(node_tree, path="", ancestors=frozenset(), parents=()):
    """Yield (node, path, parents) for every node, including in node groups.

    `parents` holds the group nodes that were entered to reach the node,
    outermost first. It is needed to find the way back out of a group.
    """
    if node_tree is None or node_tree in ancestors:
        return

    ancestors = ancestors | {node_tree}

    for node in node_tree.nodes:
        node_path = f"{path} / {node.name}" if path else node.name
        yield node, node_path, parents

        if node.type == "GROUP":
            yield from material_nodes(
                node.node_tree,
                node_path,
                ancestors,
                parents + (node,),
            )


def is_power_of_two(value):
    return value > 0 and value & (value - 1) == 0


def duplicate_image_base(name, image_names):
    """Return the name this image looks like a copy of, or ''."""
    match = _DUPLICATE_NAME.fullmatch(name)

    if match and match.group(1) in image_names:
        return match.group(1)

    return ""


def inspect_material_image(image, *, max_size, image_names):
    """Check an image's file, size and name. Return a plain dict."""
    issues = []
    packed = bool(image.packed_file or image.packed_files)
    source = image.source
    filepath = image.filepath
    path = (
        bpy.path.abspath(filepath, library=image.library)
        if filepath
        else ""
    )
    width, height = image.size
    storage = "Packed" if packed else "External file"
    file_problem = False

    if source == "GENERATED":
        storage = "Generated"

        if not image.has_data:
            issues.append((
                "INSPECT",
                "The image has no loaded pixels. Open it in the Image Editor",
            ))

    elif source == "FILE":
        if not packed:
            if not path:
                issues.append(("FAILED", "The image has no file path"))
                file_problem = True
            elif not os.path.isfile(path):
                issues.append(("FAILED", f"Image file not found: {path}"))
                file_problem = True

    else:
        storage = f"{source.title()} / {'packed' if packed else 'external'}"
        issues.append((
            "INSPECT",
            _UNSUPPORTED_IMAGE_SOURCES.get(
                source,
                f"{source.title()} image. Check this image type manually",
            ),
        ))

    if width <= 0 or height <= 0:
        if not file_problem:
            issues.append((
                "INSPECT",
                "Image size is unavailable. Open it in the Image Editor",
            ))
    else:
        if not (is_power_of_two(width) and is_power_of_two(height)):
            issues.append((
                "INSPECT",
                f"{width} × {height} is not a power of two. "
                "Some engines resize or reject it",
            ))

        if max(width, height) > max_size:
            issues.append((
                "INSPECT",
                f"Larger than {max_size} px ({width} × {height})",
            ))

    if image.is_dirty:
        issues.append(("INSPECT", "The image has unsaved changes"))

    if image.is_multiview:
        issues.append(("INSPECT", "Only the main image view is checked"))

    base = duplicate_image_base(image.name, image_names)

    if base:
        issues.append((
            "INSPECT",
            f"Looks like a copy of '{base}'. Reuse that image if it is "
            "the same",
        ))

    return dict(
        issues=issues,
        width=width,
        height=height,
        storage=storage,
        filepath=path,
        color_space=image.colorspace_settings.name,
    )


# Nodes that take a color and give a color back. The image only counts as
# passing through when it enters one of the listed inputs: a Mix Factor or a
# Gamma value is data, and a Color Ramp or Math node turns a value into
# something else, so those are not followed.
COLOR_PASSTHROUGH_INPUTS = {
    "REROUTE": None,
    "INVERT": {"Color"},
    "GAMMA": {"Color"},
    "HUE_SAT": {"Color"},
    "BRIGHTCONTRAST": {"Color"},
    "CURVE_RGB": {"Color"},
    "MIX": {"A", "B"},
    "MIX_RGB": {"Color1", "Color2"},
}

# Nodes that split a color into single channels. They are followed, because
# that is how packed maps (occlusion, roughness, metallic in R, G, B) are
# read, but a single channel reaching a color input is ambiguous.
CHANNEL_SPLIT_INPUTS = {
    "SEPRGB": {"Image"},
    "SEPARATE_COLOR": {"Color"},
}

MAX_GROUP_DEPTH = 16


def passes_color(target, link):
    """Whether an image's color arrives intact at the end of this link."""
    inputs = COLOR_PASSTHROUGH_INPUTS.get(target.type, False)

    if inputs is False:
        return False

    if inputs is not None and link.to_socket.name not in inputs:
        return False

    # The Mix node's A and B inputs also exist as number and vector versions.
    return target.type != "MIX" or getattr(link.to_socket, "type", "") == "RGBA"


def matching_sockets(sockets, socket):
    """Find the sockets on the other side of a group boundary.

    Group sockets pair up by identifier, which survives renaming.
    """
    identifier = getattr(socket, "identifier", None)

    if identifier:
        found = [item for item in sockets if item.identifier == identifier]

        if found:
            return found

    return [item for item in sockets if item.name == socket.name]


def image_color_uses(node, parents=()):
    """Trace where this image node's color goes.

    Follows the color through node groups (in and out), through nodes that
    keep it a color, and through channel splitting. Returns
    (uses, unresolved): the shader inputs it is known to feed, and the
    names of nodes it reaches that were not classified.
    """
    uses = set()
    unresolved = set()
    output = node.outputs.get("Color")
    pending = (
        [(link, parents, False) for link in output.links] if output else []
    )
    visited = set()

    def follow(sockets, chain, split):
        pending.extend(
            (link, chain, split) for item in sockets for link in item.links
        )

    while pending:
        link, chain, split = pending.pop()
        target = link.to_node
        socket = link.to_socket.name
        key = (target, socket, chain, split)

        if key in visited:
            continue

        visited.add(key)

        if target.type == "BSDF_PRINCIPLED" and (
            socket == "Base Color" or socket in {"Emission", "Emission Color"}
        ):
            if split:
                unresolved.add(f"{target.name} / {socket} (one channel)")
            else:
                uses.add(
                    "Base Color" if socket == "Base Color" else "Emission Color"
                )

        elif target.type == "BSDF_PRINCIPLED" and socket in {
            "Roughness",
            "Metallic",
        }:
            uses.add(socket)

        elif target.type == "NORMAL_MAP" and socket == "Color":
            uses.add("Normal Map")

        elif target.type == "BUMP" and socket == "Height":
            uses.add("Bump Height")

        elif target.type == "DISPLACEMENT" and socket == "Height":
            uses.add("Displacement Height")

        elif target.type == "VECTOR_DISPLACEMENT" and socket == "Vector":
            uses.add("Vector Displacement")

        elif target.type == "OUTPUT_MATERIAL" and socket == "Displacement":
            uses.add("Material Displacement")

        elif target.type == "GROUP":
            inside = target.node_tree
            entries = [
                item
                for group_input in (inside.nodes if inside else ())
                if group_input.type == "GROUP_INPUT"
                for item in matching_sockets(
                    group_input.outputs,
                    link.to_socket,
                )
            ]

            if entries and len(chain) < MAX_GROUP_DEPTH:
                follow(entries, chain + (target,), split)
            else:
                unresolved.add(target.name)

        elif target.type == "GROUP_OUTPUT" and chain:
            follow(
                matching_sockets(chain[-1].outputs, link.to_socket),
                chain[:-1],
                split,
            )

        elif socket in CHANNEL_SPLIT_INPUTS.get(target.type, ()):
            follow(target.outputs, chain, True)

        elif passes_color(target, link):
            follow(target.outputs, chain, split)

        else:
            unresolved.add(
                f"{target.name} / {socket}"
                if target.type in {"BSDF_PRINCIPLED", "MIX", "MIX_RGB"}
                else target.name
            )

    return uses, unresolved


def image_color_space_issues(node, image, parents=()):
    """Compare the image's color space with how its color is used."""
    uses, unresolved = image_color_uses(node, parents)
    color_uses = uses & COLOR_USES
    data_uses = uses - COLOR_USES
    is_data = image.colorspace_settings.is_data
    issues = []

    if color_uses and data_uses:
        issues.append((
            "INSPECT",
            f"Used for color ({', '.join(sorted(color_uses))}) and for data "
            f"({', '.join(sorted(data_uses))}). One image can't be both. "
            "Load the file twice, one set to sRGB and one to Non-Color",
        ))
    elif data_uses and not is_data:
        for use in sorted(data_uses):
            issues.append((
                "INSPECT",
                f"Used for {use}. Usually needs Non-Color",
            ))
    elif color_uses and is_data:
        for use in sorted(color_uses):
            issues.append((
                "INSPECT",
                f"Used for {use} but set to Non-Color. "
                "Check this setting",
            ))

    color_output = node.outputs.get("Color")
    names = ", ".join(sorted(unresolved))

    if not uses and (unresolved or (color_output and color_output.is_linked)):
        issues.append((
            "INSPECT",
            "Cannot tell how this image is used"
            + (f" (goes through: {names})" if names else "")
            + ". Check its Color Space",
        ))
    elif unresolved:
        issues.append((
            "INSPECT",
            f"Also feeds {names}, which was not checked. "
            "Check its Color Space manually",
        ))

    return issues


def image_uv_issues(obj, node):
    """Check which UV map or coordinates this texture uses."""
    layers = obj.data.uv_layers
    vector = node.inputs.get("Vector")
    pending = list(vector.links) if vector else []

    if not pending:
        if layers:
            return []

        return [(
            "FAILED",
            "This texture needs UVs, but the mesh has no UV map",
        )]

    issues = []
    visited = set()

    while pending:
        link = pending.pop()
        source = link.from_node

        if source in visited:
            continue

        visited.add(source)

        if source.type == "UVMAP":
            if source.from_instancer:
                issues.append((
                    "INSPECT",
                    "UVs come from an instance. Check them manually",
                ))
            elif source.uv_map and layers.get(source.uv_map) is None:
                issues.append((
                    "FAILED",
                    f"UV map '{source.uv_map}' is missing",
                ))
            elif not source.uv_map and not layers:
                issues.append((
                    "FAILED",
                    "The UV Map node needs UVs, but the mesh has no UV map",
                ))

        elif source.type == "TEX_COORD":
            if getattr(source, "from_instancer", False):
                issues.append((
                    "INSPECT",
                    "Coordinates come from an instance. "
                    "Check them manually",
                ))
            elif link.from_socket.name == "UV":
                if not layers:
                    issues.append((
                        "FAILED",
                        "The Texture Coordinate node needs UVs, "
                        "but the mesh has no UV map",
                    ))
            else:
                issues.append((
                    "INSPECT",
                    f"{link.from_socket.name} coordinates: "
                    "verify the exported texture mapping",
                ))

        elif source.type in {"MAPPING", "REROUTE"}:
            input_socket = (
                source.inputs.get("Vector")
                if source.type == "MAPPING"
                else source.inputs[0]
            )

            if input_socket and input_socket.links:
                pending.extend(input_socket.links)
            else:
                issues.append((
                    "INSPECT",
                    "The coordinate input is not connected",
                ))

        else:
            issues.append((
                "INSPECT",
                f"Coordinates pass through node '{source.name}'. "
                "Check its mapping manually",
            ))

    return issues


def inspect_texture_node(
    obj,
    node,
    path,
    parents,
    *,
    image_cache,
    max_size,
    image_names,
):
    """Check one image texture node. Return a plain dict."""
    image = node.image

    if image is None:
        return dict(
            name="No image",
            status="INSPECT",
            message=f"Node '{node.name}' has no image assigned",
            node_path=path,
            node_chain=encode_chain(parents, node),
            width=0,
            height=0,
            color_space="",
            storage="",
            filepath="",
            image=None,
            failures=[],
        )

    if image not in image_cache:
        image_cache[image] = inspect_material_image(
            image,
            max_size=max_size,
            image_names=image_names,
        )

    details = image_cache[image]
    issues = list(details["issues"])

    if node.type == "TEX_IMAGE":
        issues.extend(image_uv_issues(obj, node))
    else:
        issues.append((
            "INSPECT",
            "Environment texture. Check its GLB export manually",
        ))

    issues.extend(image_color_space_issues(node, image, parents))

    if not any(output.is_linked for output in node.outputs):
        issues.append((
            "INSPECT",
            "The image node is not connected to anything",
        ))

    status, message = combine_issues(issues)

    return dict(
        name=image.name,
        status=status,
        message=message,
        node_path=path,
        node_chain=encode_chain(parents, node),
        width=details["width"],
        height=details["height"],
        color_space=details["color_space"],
        storage=details["storage"],
        filepath=details["filepath"],
        image=image,
        failures=[
            text for status, text in issues if status == "FAILED"
        ],
    )


def normal_map_issues(obj, node, path):
    """Check a normal map node's space and UV map."""
    layers = obj.data.uv_layers

    if node.space != "TANGENT":
        return [(
            "INSPECT",
            f"{path}: normal map uses {node.space} space. "
            "Check GLB support",
        )]

    if node.uv_map and layers.get(node.uv_map) is None:
        return [("FAILED", f"{path}: UV map '{node.uv_map}' is missing")]

    if not layers:
        return [(
            "FAILED",
            f"{path}: normal map needs UVs, but the mesh has no UV map",
        )]

    return []


def inspect_material(obj, material, *, image_cache, max_size, image_names):
    """Check one material's node tree. Return (status, message, textures)."""
    if material.node_tree is None:
        return (
            "INSPECT",
            "The material has no node tree. Check the exported appearance",
            [],
        )

    issues = []

    if not getattr(material, "use_nodes", True):
        issues.append((
            "INSPECT",
            "Use Nodes is off. Check the exported appearance",
        ))

    if not any(
        node.type == "OUTPUT_MATERIAL" and node.is_active_output
        for node in material.node_tree.nodes
    ):
        issues.append(("INSPECT", "No active Material Output node"))

    textures = []

    for node, path, parents in material_nodes(material.node_tree):
        if node.type == "NORMAL_MAP":
            issues.extend(normal_map_issues(obj, node, path))

        if node.type.startswith("TEX_") and node.type not in {
            "TEX_IMAGE",
            "TEX_ENVIRONMENT",
            "TEX_COORD",
        }:
            issues.append((
                "INSPECT",
                f"{path}: procedural texture. "
                "Bake it to an image if the export needs it",
            ))

        if node.type in {"TEX_IMAGE", "TEX_ENVIRONMENT"}:
            textures.append(
                inspect_texture_node(
                    obj,
                    node,
                    path,
                    parents,
                    image_cache=image_cache,
                    max_size=max_size,
                    image_names=image_names,
                )
            )

    issues.extend((texture["status"], "") for texture in textures)
    status, message = combine_issues(issues)

    return status, message, textures


def used_slot_indices(mesh):
    """Return the material slot index of every face."""
    indices = array("i", [0]) * len(mesh.polygons)
    mesh.polygons.foreach_get("material_index", indices)

    return indices


def slot_is_empty(obj, index):
    """A slot is empty when neither the object nor the mesh has a material.

    A mesh material hidden behind an object-linked slot is not deleted.
    """
    return (
        obj.material_slots[index].material is None
        and obj.data.materials[index] is None
    )


def inspect_object_materials(
    obj,
    *,
    image_cache,
    max_size=DEFAULT_MAX_TEXTURE_SIZE,
    image_names=frozenset(),
):
    """Check one mesh object's materials. Return a plain dict."""
    mesh = obj.data
    slots = obj.material_slots
    used = set(used_slot_indices(mesh))
    messages = []
    materials = []
    images = set()
    unique_materials = set()
    empty_slots = 0

    for index, slot in enumerate(slots):
        material = slot.material
        entry = dict(
            slot=index + 1,
            link=slot.link,
            material=material,
            name=material.name if material else "Empty slot",
            status="PASSED",
            message="",
            textures=[],
        )
        issues = []

        if material is None:
            if slot_is_empty(obj, index):
                empty_slots += 1
                message = (
                    "No material assigned, and faces use this slot"
                    if index in used
                    else "No material assigned, and no faces use this slot. "
                    "Remove Empty Material Slots can delete it"
                )
            else:
                hidden = mesh.materials[index]
                message = (
                    "No object-linked material assigned. "
                    f"The mesh has '{hidden.name}' in this slot, "
                    "so it is not empty and is kept"
                )

            issues.append(("INSPECT", message))
        else:
            unique_materials.add(material)

            if index not in used:
                issues.append(("INSPECT", "No faces use this slot"))

            status, message, textures = inspect_material(
                obj,
                material,
                image_cache=image_cache,
                max_size=max_size,
                image_names=image_names,
            )
            issues.append((status, message))
            entry["textures"] = textures
            images.update(
                texture["image"]
                for texture in textures
                if texture["image"] is not None
            )

        entry["status"], entry["message"] = combine_issues(issues)
        materials.append(entry)

    statuses = [entry["status"] for entry in materials]

    if not slots:
        messages.append("No material slots. Assign a material if needed")
        statuses.append("INSPECT")

    missing = sorted(index + 1 for index in used if index >= len(slots))

    if slots and missing:
        messages.append(
            "Faces use missing material slot(s): "
            + ", ".join(map(str, missing))
        )
        statuses.append("INSPECT")

    if any(modifier.show_viewport for modifier in obj.modifiers):
        messages.append(
            "Checked before modifiers. Apply modifiers and check again"
        )
        statuses.append("INSPECT")

    return dict(
        status=worst_status(statuses),
        message="\n".join(messages),
        material_count=len(unique_materials),
        image_count=len(images),
        empty_slots=empty_slots,
        materials=materials,
    )


class MaterialSlotCommitError(RuntimeError):
    """Material slots could not be restored. Use Undo."""


def material_slot_difference(obj, expected):
    """Say which material slot differs from the expected (link, material)."""
    actual = [(slot.link, slot.material) for slot in obj.material_slots]

    if len(actual) != len(expected):
        return f"Expected {len(expected)} material slots, found {len(actual)}"

    for index, ((link, material), (old_link, old_material)) in enumerate(
        zip(actual, expected),
        1,
    ):
        if link != old_link:
            return (
                f"Slot {index}: expected {old_link.title()} link, "
                f"found {link.title()}"
            )

        if material != old_material:
            name = material.name if material else "Empty"
            old_name = old_material.name if old_material else "Empty"
            return f"Slot {index}: expected '{old_name}', found '{name}'"

    return ""


def removal_blocker(obj):
    """Return why this object's slots must not be changed, or ''."""
    if not obj.is_editable:
        return "This object cannot be edited. Make it local first"

    if obj.override_library:
        return "This object is a library override. Use a local copy"

    mesh = obj.data

    if not mesh.is_editable:
        return "This mesh cannot be edited. Make it local first"

    users = mesh.users - int(mesh.use_fake_user)

    if users > 1:
        return (
            f"The mesh is shared by {users} users. "
            "Make it single user first"
        )

    if any(modifier.show_viewport for modifier in obj.modifiers):
        return "Apply enabled modifiers before removing slots"

    return ""


def rebuild_material_slots(obj, data_materials, face_indices, slots):
    """Rewrite the mesh slots, face assignments and slot links."""
    mesh = obj.data
    mesh.materials.clear()

    for material in data_materials:
        mesh.materials.append(material)

    mesh.polygons.foreach_set("material_index", face_indices)
    mesh.update()
    restore_material_links(obj, slots)


def remove_empty_material_slots(obj):
    """Remove empty slots that no faces use. Return (count, message).

    Works on the object's own mesh, so nothing is copied. If anything goes
    wrong the original slots are rebuilt. When that fails too,
    MaterialSlotCommitError tells the caller to use Undo.
    """
    mesh = obj.data
    slots = [(slot.link, slot.material) for slot in obj.material_slots]
    empty = {
        index
        for index in range(len(slots))
        if slot_is_empty(obj, index)
    }

    if not empty:
        return 0, "No empty material slots"

    blocker = removal_blocker(obj)

    if blocker:
        return 0, blocker

    data_materials = list(mesh.materials)

    face_indices = used_slot_indices(mesh)

    for face_index, index in enumerate(face_indices):
        if index < 0 or index >= len(slots):
            return 0, (
                f"Face {face_index} uses missing material slot "
                f"{index + 1}. Assign a valid slot first"
            )

    used = set(face_indices)
    removable = empty - used
    protected = empty & used

    if not removable:
        return 0, f"Kept {len(protected)} empty slot(s) used by faces"

    kept = [index for index in range(len(slots)) if index not in removable]
    remap = {old: new for new, old in enumerate(kept)}
    remaining = [slots[index] for index in kept]
    old_active = obj.active_material_index
    new_active = min(
        sum(index < old_active for index in kept),
        max(0, len(kept) - 1),
    )

    try:
        for index in sorted(removable, reverse=True):
            mesh.materials.pop(index=index)

        mesh.polygons.foreach_set(
            "material_index",
            array("i", (remap[index] for index in face_indices)),
        )
        mesh.update()
        restore_material_links(obj, remaining, new_active)

        difference = material_slot_difference(obj, remaining)

        if difference:
            raise RuntimeError(difference)

    except Exception as error:
        try:
            rebuild_material_slots(obj, data_materials, face_indices, slots)
            obj.active_material_index = old_active
            difference = material_slot_difference(obj, slots)

            if difference:
                raise RuntimeError(f"Material restore failed: {difference}")

        except Exception as recovery_error:
            raise MaterialSlotCommitError(
                f"Couldn't restore material slots: {recovery_error}. "
                "Use Undo before continuing"
            ) from error

        raise

    message = f"Removed {len(removable)} empty slot(s)"

    if protected:
        message += f". Kept {len(protected)} empty slot(s) used by faces"

    return len(removable), message

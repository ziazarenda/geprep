"""Find a node again from the names saved by Check Materials.

No bpy import: it only reads `.nodes`, `.type` and `.node_tree`, so plain
tests can run it with fake trees.
"""

import json


def encode_chain(parents, node):
    """Names of the group nodes entered (outermost first) plus the node, as JSON.

    JSON, not a joined string: a node name may contain any separator.
    """
    return json.dumps([parent.name for parent in parents] + [node.name])


def decode_chain(text):
    """The list of names, or None when `text` is empty or not a valid chain."""
    try:
        names = json.loads(text)
    except (TypeError, ValueError):
        return None

    if (
        not isinstance(names, list)
        or not names
        or not all(isinstance(name, str) for name in names)
    ):
        return None

    return names


def resolve_chain(root_tree, names):
    """Return (group_nodes, node) for a chain, starting in `root_tree`.

    Raises LookupError with a plain message when something was renamed,
    deleted or is no longer a group.
    """
    tree = root_tree
    groups = []

    for name in names[:-1]:
        group = tree.nodes.get(name) if tree is not None else None

        if group is None or group.type != "GROUP" or group.node_tree is None:
            raise LookupError(f"Group node '{name}' was not found")

        groups.append(group)
        tree = group.node_tree

    node = tree.nodes.get(names[-1]) if tree is not None else None

    if node is None:
        raise LookupError(f"Node '{names[-1]}' was not found")

    return groups, node

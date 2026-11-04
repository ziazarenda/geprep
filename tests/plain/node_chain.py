"""Check how a node is found again from the names saved by Check Materials (no Blender needed)."""
import importlib.util
import types
from pathlib import Path

path = Path(__file__).resolve().parents[2] / "geprep" / "helpers" / "node_chain.py"
spec = importlib.util.spec_from_file_location("node_chain", path)
node_chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node_chain)
encode_chain, decode_chain, resolve_chain = (
    node_chain.encode_chain, node_chain.decode_chain, node_chain.resolve_chain)


class Nodes(dict):
    pass


def tree(*nodes):
    return types.SimpleNamespace(nodes=Nodes({n.name: n for n in nodes}))


def node(name, kind="TEX_IMAGE", inner=None):
    return types.SimpleNamespace(name=name, type=kind, node_tree=inner)


checks = 0


def check(condition, message):
    global checks
    checks += 1
    assert condition, message


def raises(function, *args):
    try:
        function(*args)
    except LookupError as error:
        return str(error)
    return None


# --- a node at the top level
image = node("Image Texture")
root = tree(image, node("Other"))
text = encode_chain([], image)
check(decode_chain(text) == ["Image Texture"], "plain chain round-trips")
groups, found = resolve_chain(root, decode_chain(text))
check(groups == [] and found is image, "top-level node found")

# --- a node inside two nested groups
deep = node("Image Texture")
inner = tree(deep)
group_b = node("Group B", "GROUP", inner)
middle = tree(group_b)
group_a = node("Group A", "GROUP", middle)
root = tree(group_a)
text = encode_chain([group_a, group_b], deep)
check(decode_chain(text) == ["Group A", "Group B", "Image Texture"], "nested chain keeps order")
groups, found = resolve_chain(root, decode_chain(text))
check(groups == [group_a, group_b] and found is deep, "nested node found, groups returned outermost first")

# --- names that would break a joined string
odd = node("A / B")
root = tree(odd)
check(resolve_chain(root, decode_chain(encode_chain([], odd)))[1] is odd, "name containing ' / ' still found")
odd = node('quote " and \\ slash')
root = tree(odd)
check(resolve_chain(root, decode_chain(encode_chain([], odd)))[1] is odd, "quotes and backslashes survive")

# --- things that changed since the check
root = tree(node("Other"))
check("'Image Texture' was not found" in raises(resolve_chain, root, ["Image Texture"]), "renamed or deleted node is reported")
root = tree(node("Group A", "TEX_IMAGE"))
check("Group node 'Group A' was not found" in raises(resolve_chain, root, ["Group A", "X"]), "a non-group in the chain is reported")
root = tree(node("Group A", "GROUP", None))
check("Group node 'Group A' was not found" in raises(resolve_chain, root, ["Group A", "X"]), "a group without a tree is reported")
check("'X' was not found" in raises(resolve_chain, tree(node("Group A", "GROUP", tree())), ["Group A", "X"]), "missing node inside a group is reported")

# --- stored text that is empty or damaged (old results, hand edits)
for bad in ("", "not json", "[]", "{}", "[1, 2]", '["ok", 3]', None):
    check(decode_chain(bad) is None, f"bad chain {bad!r} is rejected")

print(f"node_chain: {checks} checks passed")

"""Plain-Python tests for helpers/progress.py (run: python3 progress_logic.py)."""
import importlib.util
import pathlib
from types import SimpleNamespace

path = pathlib.Path(__file__).resolve().parent.parent.parent / "geprep" / "helpers" / "progress.py"
spec = importlib.util.spec_from_file_location("progress", path)
progress = importlib.util.module_from_spec(spec)
spec.loader.exec_module(progress)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


class Manager:
    def __init__(self):
        self.calls = []

    def progress_begin(self, low, high):
        self.calls.append(("begin", low, high))

    def progress_update(self, value):
        self.calls.append(("update", value))

    def progress_end(self):
        self.calls.append(("end",))


def run(items, **options):
    manager = Manager()
    return manager, SimpleNamespace(window_manager=manager), items, options


manager, context, items, options = run(["a", "b", "c"])
seen = list(progress.with_progress(context, items))
check(seen == ["a", "b", "c"], "Every item is passed through in order")
check(manager.calls == [("begin", 0, 3), ("update", 1), ("update", 2), ("update", 3), ("end",)],
      "Progress runs 0 to 3 and is cleared at the end")

manager, context, items, _ = run(["only"])
check(list(progress.with_progress(context, items)) == ["only"] and manager.calls == [],
      "A single item shows no progress by default")

manager, context, items, _ = run(["only"])
list(progress.with_progress(context, items, minimum=1))
check(manager.calls == [("begin", 0, 1), ("update", 1), ("end",)],
      "minimum=1 shows progress even for one item")

manager, context, items, _ = run([])
check(list(progress.with_progress(context, items, minimum=1)) == [] and manager.calls == [],
      "An empty list never starts progress")

manager, context, items, _ = run(["a", "b", "c"])
for item in progress.with_progress(context, items):
    if item == "b":
        continue
check(manager.calls[-3:] == [("update", 2), ("update", 3), ("end",)],
      "continue still counts the item as done")

manager, context, items, _ = run(["a", "b", "c"])
for item in progress.with_progress(context, items):
    if item == "b":
        break
check(manager.calls[0] == ("begin", 0, 3) and manager.calls[-1] == ("end",),
      "A loop that stops early still clears the progress")


def failing(manager, context):
    for item in progress.with_progress(context, ["a", "b"]):
        raise RuntimeError("boom")


manager, context, _, _ = run([])
try:
    failing(manager, context)
except RuntimeError:
    pass
check(manager.calls[-1] == ("end",), "An exception inside the loop still clears the progress")

manager, context, items, _ = run(iter(["a", "b"]))
check(list(progress.with_progress(context, items)) == ["a", "b"] and manager.calls[0] == ("begin", 0, 2),
      "A generator of items works too")

print("ALL PROGRESS TESTS PASSED")

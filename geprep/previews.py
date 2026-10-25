from bpy.utils import previews
from .constants import ICONS_DIR


preview_collections = {}


def get_icon(name: str) -> int:
    return preview_collections["icons"][name].icon_id


def register():
    collection = previews.new()

    try:
        for path in sorted(ICONS_DIR.iterdir()):
            if not path.is_file() or path.suffix.lower() != ".png":
                continue

            try:
                collection.load(path.stem, str(path), "IMAGE")
            except Exception as error:
                error.add_note(f"GEPrep: failed to load icon {str(path)!r}")
                raise

    except Exception:
        previews.remove(collection)
        raise

    preview_collections["icons"] = collection


def unregister():
    for collection in preview_collections.values():
        previews.remove(collection)

    preview_collections.clear()

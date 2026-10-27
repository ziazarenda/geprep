import re


_NUMERIC_SUFFIX = re.compile(r"\.\d{3,}$")


def validate_name(name: str) -> str:
    """Validate and normalize the requested new name."""
    result = name.strip()

    if not result:
        raise ValueError("Enter a Name first")

    return result


def replace_name(name: str, find: str, replacement: str) -> str:
    """Replace case-sensitive text in an object name."""
    if not find:
        raise ValueError("Enter the text to find first")

    result = name.replace(find, replacement)

    if not result.strip():
        raise ValueError(
            f"Replacing {find!r} in {name!r} would produce an empty name"
        )

    return result


def remove_numeric_suffix(name: str) -> str:
    """Remove a trailing Blender-style suffix such as .001."""
    result = _NUMERIC_SUFFIX.sub("", name)

    if not result.strip():
        raise ValueError(
            f"Removing the numeric suffix from {name!r} would produce an empty name"
        )

    return result


def reserve_name(
    requested: str,
    reserved: set[str],
    *,
    add_suffix: bool = True,
) -> str | None:
    """Reserve an unused name, or return None when numbering is disabled."""
    if requested not in reserved:
        reserved.add(requested)
        return requested

    if not add_suffix:
        return None

    stem = remove_numeric_suffix(requested)
    number = 1

    while True:
        candidate = f"{stem}.{number:03d}"

        if candidate not in reserved:
            reserved.add(candidate)
            return candidate

        number += 1


def plan_renames(
    names,
    existing_names,
    action,
    *,
    new_name="",
    find="",
    replacement="",
):
    """Plan renames without modifying Blender objects."""
    if action not in {"NEW", "REPLACE", "SUFFIX"}:
        raise ValueError(f"Unknown naming action: {action!r}")

    requested_name = validate_name(new_name) if action == "NEW" else ""

    if action == "REPLACE" and not find:
        raise ValueError("Enter the text to find first")

    names = sorted(names, key=lambda name: (name.casefold(), name))
    reserved = set(existing_names)
    reserved.update(names)
    plans = []

    for old in names:
        plan = {
            "old": old,
            "new": old,
            "status": "SKIPPED",
            "message": "",
        }
        plans.append(plan)

        try:
            if action == "NEW":
                requested = requested_name
            elif action == "REPLACE":
                requested = replace_name(old, find, replacement)
            else:
                requested = remove_numeric_suffix(old)
        except ValueError as error:
            plan["message"] = str(error)
            continue

        if requested == old:
            plan["message"] = "Name is unchanged"
            continue

        if (
            action == "NEW"
            and _NUMERIC_SUFFIX.search(old)
            and remove_numeric_suffix(old) == requested
        ):
            plan["message"] = "Already uses this name with a number"
            continue

        candidate = reserve_name(
            requested,
            reserved,
            add_suffix=action != "SUFFIX",
        )

        if candidate is None:
            plan["message"] = f"Name {requested!r} is already in use"
            continue

        plan["new"] = candidate
        plan["status"] = "CHANGED"

        if candidate != requested:
            plan["message"] = "Added a number because this name is taken"

    return plans


class RenameRecoveryError(RuntimeError):
    """The original name could not be restored."""


def assign_object_name(obj, requested: str) -> None:
    """Assign the exact requested name, restoring the original on failure."""
    original = obj.name

    try:
        obj.name = requested

        if obj.name != requested:
            raise RuntimeError(
                f"Requested name {requested!r}, "
                f"but Blender assigned {obj.name!r}"
            )

    except Exception as error:
        error.add_note(
            f"GEPrep: failed to rename {original!r} to {requested!r}"
        )

        try:
            obj.name = original

            if obj.name != original:
                raise RuntimeError(
                    f"Requested original name {original!r}, "
                    f"but Blender assigned {obj.name!r}"
                )

        except Exception as recovery_error:
            raise RenameRecoveryError(
                f"Could not restore {original!r}: {recovery_error}. "
                "Use Undo before continuing"
            ) from error

        raise

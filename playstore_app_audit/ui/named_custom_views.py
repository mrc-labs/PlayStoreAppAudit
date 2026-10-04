from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID, uuid4

SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
MAX_VIEWS_PER_FAMILY = 3
MAX_NAME_LENGTH = 80


class NamedViewError(ValueError):
    pass


class NamedViewLimitError(NamedViewError):
    pass


class DuplicateNamedViewError(NamedViewError):
    pass


def empty_family() -> dict[str, object]:
    return {"active_view_id": "", "views": []}


def empty_layouts() -> dict[str, object]:
    return {
        "schema_version": SCHEMA_VERSION,
        "phone_app_list": empty_family(),
        "local_apk": empty_family(),
    }


def normalise_name(value: object) -> str:
    return " ".join(str(value or "").split())


def _validated_name(value: object) -> str:
    name = normalise_name(value)
    if not name:
        raise NamedViewError("View name cannot be empty.")
    if len(name) > MAX_NAME_LENGTH:
        raise NamedViewError(f"View name cannot exceed {MAX_NAME_LENGTH} characters.")
    return name


def _valid_uuid(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        return str(UUID(text)) == text.lower()
    except (ValueError, AttributeError):
        return False


def is_supported(layouts: object) -> bool:
    return (
        isinstance(layouts, dict)
        and type(layouts.get("schema_version")) is int
        and layouts.get("schema_version") == SCHEMA_VERSION
    )


def is_legacy_v1(layouts: object) -> bool:
    return (
        isinstance(layouts, dict)
        and type(layouts.get("schema_version")) is int
        and layouts.get("schema_version") == LEGACY_SCHEMA_VERSION
    )


def family_state(layouts: object, family: str) -> dict[str, object] | None:
    if not is_supported(layouts):
        return None
    assert isinstance(layouts, dict)
    raw = layouts.get(family)
    if not isinstance(raw, dict):
        return None
    views = raw.get("views")
    active = raw.get("active_view_id")
    if not isinstance(views, list) or not isinstance(active, str):
        return None
    return raw


def view_records(layouts: object, family: str) -> list[dict[str, Any]]:
    state = family_state(layouts, family)
    if state is None:
        return []
    raw_views = state.get("views", [])
    assert isinstance(raw_views, list)
    if len(raw_views) > MAX_VIEWS_PER_FAMILY:
        return []
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    for raw in raw_views:
        if not isinstance(raw, dict):
            return []
        view_id = str(raw.get("id") or "").strip().lower()
        name = normalise_name(raw.get("name"))
        name_key = name.casefold()
        if (
            not _valid_uuid(view_id)
            or not name
            or len(name) > MAX_NAME_LENGTH
            or view_id in seen_ids
            or name_key in seen_names
        ):
            return []
        columns = raw.get("columns")
        order = raw.get("order")
        widths = raw.get("widths")
        if not isinstance(columns, list) or not isinstance(order, list) or not isinstance(widths, dict):
            return []
        seen_ids.add(view_id)
        seen_names.add(name_key)
        records.append(
            {
                "id": view_id,
                "name": name,
                "columns": list(columns),
                "order": list(order),
                "widths": dict(widths),
            }
        )
    return records


def active_view(layouts: object, family: str) -> dict[str, Any] | None:
    state = family_state(layouts, family)
    if state is None:
        return None
    active_id = str(state.get("active_view_id") or "").strip().lower()
    if not active_id:
        return None
    return next((view for view in view_records(layouts, family) if view["id"] == active_id), None)


def _ensure_editable(layouts: object, family: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not is_supported(layouts):
        raise NamedViewError("Unsupported named-view schema.")
    updated = deepcopy(layouts)
    assert isinstance(updated, dict)
    state = updated.get(family)
    if not isinstance(state, dict) or not isinstance(state.get("views"), list):
        raise NamedViewError("Malformed named-view family.")
    if not isinstance(state.get("active_view_id"), str):
        raise NamedViewError("Malformed named-view active id.")
    if len(view_records(updated, family)) != len(state["views"]):
        raise NamedViewError("Malformed named-view record.")
    return updated, state


def create_view(
    layouts: object,
    family: str,
    *,
    name: object,
    columns: list[str],
    order: list[str],
    widths: dict[str, int],
    activate: bool = True,
) -> tuple[dict[str, Any], str]:
    updated, state = _ensure_editable(layouts, family)
    views = state["views"]
    assert isinstance(views, list)
    if len(views) >= MAX_VIEWS_PER_FAMILY:
        raise NamedViewLimitError(f"Maximum {MAX_VIEWS_PER_FAMILY} named views per source family.")
    clean_name = _validated_name(name)
    if any(normalise_name(item.get("name")).casefold() == clean_name.casefold() for item in views):
        raise DuplicateNamedViewError("A view with this name already exists.")
    view_id = str(uuid4())
    views.append(
        {
            "id": view_id,
            "name": clean_name,
            "columns": list(columns),
            "order": list(order),
            "widths": dict(widths),
        }
    )
    if activate:
        state["active_view_id"] = view_id
    return updated, view_id


def update_view(
    layouts: object,
    family: str,
    view_id: str,
    *,
    columns: list[str],
    order: list[str],
    widths: dict[str, int],
) -> dict[str, Any]:
    updated, state = _ensure_editable(layouts, family)
    target = str(view_id or "").strip().lower()
    for item in state["views"]:
        if str(item.get("id") or "").strip().lower() == target:
            item["columns"] = list(columns)
            item["order"] = list(order)
            item["widths"] = dict(widths)
            return updated
    raise NamedViewError("Named view does not exist.")


def rename_view(layouts: object, family: str, view_id: str, name: object) -> dict[str, Any]:
    updated, state = _ensure_editable(layouts, family)
    clean_name = _validated_name(name)
    target = str(view_id or "").strip().lower()
    for item in state["views"]:
        item_id = str(item.get("id") or "").strip().lower()
        if item_id != target and normalise_name(item.get("name")).casefold() == clean_name.casefold():
            raise DuplicateNamedViewError("A view with this name already exists.")
    for item in state["views"]:
        if str(item.get("id") or "").strip().lower() == target:
            item["name"] = clean_name
            return updated
    raise NamedViewError("Named view does not exist.")


def delete_view(layouts: object, family: str, view_id: str) -> tuple[dict[str, Any], bool]:
    updated, state = _ensure_editable(layouts, family)
    target = str(view_id or "").strip().lower()
    before = list(state["views"])
    remaining = [
        item
        for item in before
        if str(item.get("id") or "").strip().lower() != target
    ]
    if len(remaining) == len(before):
        raise NamedViewError("Named view does not exist.")
    state["views"] = remaining
    was_active = str(state.get("active_view_id") or "").strip().lower() == target
    if was_active:
        state["active_view_id"] = ""
    return updated, was_active


def select_view(layouts: object, family: str, view_id: str) -> dict[str, Any]:
    updated, state = _ensure_editable(layouts, family)
    target = str(view_id or "").strip().lower()
    if not any(str(item.get("id") or "").strip().lower() == target for item in state["views"]):
        raise NamedViewError("Named view does not exist.")
    state["active_view_id"] = target
    return updated

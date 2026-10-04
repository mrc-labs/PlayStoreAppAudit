from __future__ import annotations

from copy import deepcopy

import pytest

from playstore_app_audit.domain import named_custom_views


def _layout() -> dict[str, object]:
    return named_custom_views.empty_layouts()


def _payload() -> tuple[list[str], list[str], dict[str, int]]:
    return (
        ["criticality", "package_name", "play_title"],
        ["play_title", "criticality", "package_name"],
        {"package_name": 320, "play_title": 280},
    )


def test_create_select_update_rename_delete_round_trip() -> None:
    layouts = _layout()
    columns, order, widths = _payload()

    layouts, view_id = named_custom_views.create_view(
        layouts,
        "phone_app_list",
        name="  Work   View  ",
        columns=columns,
        order=order,
        widths=widths,
    )

    assert named_custom_views.active_view(layouts, "phone_app_list") == {
        "id": view_id,
        "name": "Work View",
        "columns": columns,
        "order": order,
        "widths": widths,
    }

    renamed = named_custom_views.rename_view(
        layouts, "phone_app_list", view_id, "Daily"
    )
    assert named_custom_views.active_view(renamed, "phone_app_list")["name"] == "Daily"

    updated = named_custom_views.update_view(
        renamed,
        "phone_app_list",
        view_id,
        columns=["criticality", "package_name", "play_category"],
        order=["play_category", "criticality", "package_name"],
        widths={"play_category": 170},
    )
    active = named_custom_views.active_view(updated, "phone_app_list")
    assert active is not None
    assert active["id"] == view_id
    assert active["columns"][-1] == "play_category"

    deleted, was_active = named_custom_views.delete_view(
        updated, "phone_app_list", view_id
    )
    assert was_active is True
    assert named_custom_views.active_view(deleted, "phone_app_list") is None
    assert named_custom_views.view_records(deleted, "phone_app_list") == []


@pytest.mark.parametrize("family", ["phone_app_list", "local_apk"])
def test_three_view_limit_is_independent_per_family(family: str) -> None:
    layouts = _layout()
    columns, order, widths = _payload()
    for index in range(3):
        layouts, _ = named_custom_views.create_view(
            layouts,
            family,
            name=f"Phone {index + 1}",
            columns=columns,
            order=order,
            widths=widths,
        )

    with pytest.raises(named_custom_views.NamedViewLimitError):
        named_custom_views.create_view(
            layouts,
            family,
            name="Phone 4",
            columns=columns,
            order=order,
            widths=widths,
        )

    sibling = "local_apk" if family == "phone_app_list" else "phone_app_list"
    layouts, local_id = named_custom_views.create_view(
        layouts,
        sibling,
        name="APK 1",
        columns=["criticality", "package_name", "local_apk_file_name"],
        order=["local_apk_file_name", "criticality", "package_name"],
        widths={"local_apk_file_name": 300},
    )
    assert named_custom_views.active_view(layouts, sibling)["id"] == local_id
    assert len(named_custom_views.view_records(layouts, family)) == 3


@pytest.mark.parametrize("field,value", [
    ("id", "12345678-1234-1234-8234-123456789abc"),
    ("name", 42), ("name", ""), ("columns", []),
    ("columns", [{}]), ("order", [[]]), ("widths", []),
])
def test_corrupt_records_block_reads_and_mutations_without_rewriting(field: str, value: object) -> None:
    columns, order, widths = _payload()
    layouts, view_id = named_custom_views.create_view(
        _layout(), "phone_app_list", name="Valid", columns=columns, order=order, widths=widths,
    )
    layouts["phone_app_list"]["views"][0][field] = value
    before = deepcopy(layouts)
    assert not named_custom_views.is_supported(layouts)
    assert named_custom_views.view_records(layouts, "phone_app_list") == []
    assert named_custom_views.active_view(layouts, "phone_app_list") is None
    with pytest.raises(named_custom_views.NamedViewError):
        named_custom_views.rename_view(layouts, "phone_app_list", view_id, "New name")
    with pytest.raises(named_custom_views.NamedViewError):
        named_custom_views.create_view(
            layouts, "local_apk", name="Sibling", columns=columns, order=order, widths=widths,
        )
    assert layouts == before


def test_uuid4_identity_and_duplicate_creation_name_validation() -> None:
    from uuid import UUID

    columns, order, widths = _payload()
    layouts, view_id = named_custom_views.create_view(
        _layout(), "phone_app_list", name=" A\t B ", columns=columns, order=order, widths=widths,
    )
    assert UUID(view_id).version == 4
    with pytest.raises(named_custom_views.DuplicateNamedViewError):
        named_custom_views.create_view(
            layouts, "phone_app_list", name="a b", columns=columns, order=order, widths=widths,
        )
    layouts, sibling = named_custom_views.create_view(
        layouts, "local_apk", name="a b", columns=columns, order=order, widths=widths,
    )
    assert UUID(sibling).version == 4 and sibling != view_id


def test_names_are_required_unique_case_insensitively_and_stable_ids_survive_rename() -> None:
    layouts = _layout()
    columns, order, widths = _payload()
    layouts, first_id = named_custom_views.create_view(
        layouts,
        "phone_app_list",
        name="Audit",
        columns=columns,
        order=order,
        widths=widths,
    )
    layouts, second_id = named_custom_views.create_view(
        layouts,
        "phone_app_list",
        name="Technical Review",
        columns=columns,
        order=order,
        widths=widths,
    )

    with pytest.raises(named_custom_views.DuplicateNamedViewError):
        named_custom_views.rename_view(
            layouts, "phone_app_list", second_id, "  AUDIT "
        )

    renamed = named_custom_views.rename_view(
        layouts, "phone_app_list", first_id, "Audit Daily"
    )
    assert any(
        view["id"] == first_id and view["name"] == "Audit Daily"
        for view in named_custom_views.view_records(renamed, "phone_app_list")
    )

    with pytest.raises(named_custom_views.NamedViewError):
        named_custom_views.create_view(
            layouts,
            "local_apk",
            name="   ",
            columns=columns,
            order=order,
            widths=widths,
        )


def test_operations_are_non_mutating_until_caller_persists_result() -> None:
    layouts = _layout()
    original = deepcopy(layouts)
    columns, order, widths = _payload()

    updated, _ = named_custom_views.create_view(
        layouts,
        "phone_app_list",
        name="Draft",
        columns=columns,
        order=order,
        widths=widths,
    )

    assert layouts == original
    assert updated != original


@pytest.mark.parametrize(
    "invalid",
    [
        {"schema_version": 3, "phone_app_list": {}, "local_apk": {}},
        {"schema_version": "2", "phone_app_list": {}, "local_apk": {}},
        {
            "schema_version": 2,
            "phone_app_list": {"active_view_id": "", "views": "bad"},
            "local_apk": {"active_view_id": "", "views": []},
        },
    ],
)
def test_future_or_malformed_state_is_not_editable(invalid: dict[str, object]) -> None:
    before = deepcopy(invalid)
    columns, order, widths = _payload()

    with pytest.raises(named_custom_views.NamedViewError):
        named_custom_views.create_view(
            invalid,
            "phone_app_list",
            name="Should fail",
            columns=columns,
            order=order,
            widths=widths,
        )

    assert invalid == before


def test_selecting_views_is_family_local() -> None:
    layouts = _layout()
    columns, order, widths = _payload()
    layouts, phone_a = named_custom_views.create_view(
        layouts,
        "phone_app_list",
        name="Phone A",
        columns=columns,
        order=order,
        widths=widths,
    )
    layouts, phone_b = named_custom_views.create_view(
        layouts,
        "phone_app_list",
        name="Phone B",
        columns=columns,
        order=order,
        widths=widths,
    )
    layouts, apk = named_custom_views.create_view(
        layouts,
        "local_apk",
        name="APK",
        columns=["criticality", "package_name", "local_apk_file_name"],
        order=["criticality", "package_name", "local_apk_file_name"],
        widths={"local_apk_file_name": 240},
    )

    layouts = named_custom_views.select_view(layouts, "phone_app_list", phone_a)
    assert named_custom_views.active_view(layouts, "phone_app_list")["id"] == phone_a
    assert named_custom_views.active_view(layouts, "local_apk")["id"] == apk

    layouts = named_custom_views.select_view(layouts, "phone_app_list", phone_b)
    assert named_custom_views.active_view(layouts, "phone_app_list")["id"] == phone_b
    assert named_custom_views.active_view(layouts, "local_apk")["id"] == apk


def test_overlong_names_and_overfull_or_duplicate_persisted_state_fail_conservatively() -> None:
    columns, order, widths = _payload()
    layouts = _layout()

    with pytest.raises(named_custom_views.NamedViewError):
        named_custom_views.create_view(
            layouts,
            "phone_app_list",
            name="x" * (named_custom_views.MAX_NAME_LENGTH + 1),
            columns=columns,
            order=order,
            widths=widths,
        )

    layouts, _ = named_custom_views.create_view(
        layouts,
        "phone_app_list",
        name="One",
        columns=columns,
        order=order,
        widths=widths,
    )
    duplicate = deepcopy(layouts)
    family = duplicate["phone_app_list"]
    assert isinstance(family, dict)
    views = family["views"]
    assert isinstance(views, list)
    views.append(deepcopy(views[0]))
    assert named_custom_views.view_records(duplicate, "phone_app_list") == []

    overfull = named_custom_views.empty_layouts()
    for index in range(named_custom_views.MAX_VIEWS_PER_FAMILY):
        overfull, _ = named_custom_views.create_view(
            overfull,
            "phone_app_list",
            name=f"View {index + 1}",
            columns=columns,
            order=order,
            widths=widths,
        )
    phone = overfull["phone_app_list"]
    assert isinstance(phone, dict)
    stored = phone["views"]
    assert isinstance(stored, list)
    extra = deepcopy(stored[-1])
    extra["id"] = "12345678-1234-4234-8234-123456789abc"
    extra["name"] = "View 4"
    stored.append(extra)
    assert named_custom_views.view_records(overfull, "phone_app_list") == []

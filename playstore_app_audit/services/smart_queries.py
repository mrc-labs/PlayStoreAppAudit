from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

import playstore_app_audit.services.state as state

SCHEMA_VERSION = 1
SETTINGS_KEY = "smart_queries"
MAX_NAME_LENGTH = 80
MAX_CONDITIONS = 20


class FieldType(StrEnum):
    TEXT = "text"
    CHOICE = "choice"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"


class MatchMode(StrEnum):
    ALL = "all"
    ANY = "any"


class Operator(StrEnum):
    CONTAINS = "contains"
    DOES_NOT_CONTAIN = "does_not_contain"
    IS = "is"
    IS_NOT = "is_not"
    STARTS_WITH = "starts_with"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    EQUALS = "equals"
    DOES_NOT_EQUAL = "does_not_equal"
    GREATER_THAN = "greater_than"
    GREATER_OR_EQUAL = "greater_or_equal"
    LESS_THAN = "less_than"
    LESS_OR_EQUAL = "less_or_equal"
    IS_ON = "is_on"
    IS_BEFORE = "is_before"
    IS_AFTER = "is_after"
    WITHIN_LAST_DAYS = "within_last_days"
    IS_YES = "is_yes"
    IS_NO = "is_no"


@dataclass(frozen=True, slots=True)
class ChoiceDefinition:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    field_id: str
    label: str
    field_type: FieldType
    choices: tuple[ChoiceDefinition, ...] = ()


@dataclass(frozen=True, slots=True)
class SmartCondition:
    field: str
    operator: Operator
    value: str | int | float | None = None


@dataclass(frozen=True, slots=True)
class SmartQuery:
    query_id: str
    name: str
    match: MatchMode
    conditions: tuple[SmartCondition, ...]


TEXT_OPERATORS = (
    Operator.CONTAINS,
    Operator.DOES_NOT_CONTAIN,
    Operator.IS,
    Operator.IS_NOT,
    Operator.STARTS_WITH,
    Operator.IS_EMPTY,
    Operator.IS_NOT_EMPTY,
)
CHOICE_OPERATORS = (
    Operator.IS,
    Operator.IS_NOT,
    Operator.IS_EMPTY,
    Operator.IS_NOT_EMPTY,
)
NUMBER_OPERATORS = (
    Operator.EQUALS,
    Operator.DOES_NOT_EQUAL,
    Operator.GREATER_THAN,
    Operator.GREATER_OR_EQUAL,
    Operator.LESS_THAN,
    Operator.LESS_OR_EQUAL,
    Operator.IS_EMPTY,
    Operator.IS_NOT_EMPTY,
)
DATE_OPERATORS = (
    Operator.IS_ON,
    Operator.IS_BEFORE,
    Operator.IS_AFTER,
    Operator.WITHIN_LAST_DAYS,
    Operator.IS_EMPTY,
    Operator.IS_NOT_EMPTY,
)
BOOLEAN_OPERATORS = (Operator.IS_YES, Operator.IS_NO)

OPERATORS_BY_TYPE = {
    FieldType.TEXT: TEXT_OPERATORS,
    FieldType.CHOICE: CHOICE_OPERATORS,
    FieldType.NUMBER: NUMBER_OPERATORS,
    FieldType.DATE: DATE_OPERATORS,
    FieldType.BOOLEAN: BOOLEAN_OPERATORS,
}

OPERATOR_LABELS = {
    Operator.CONTAINS: "Contains",
    Operator.DOES_NOT_CONTAIN: "Does Not Contain",
    Operator.IS: "Is",
    Operator.IS_NOT: "Is Not",
    Operator.STARTS_WITH: "Starts With",
    Operator.IS_EMPTY: "Is Empty",
    Operator.IS_NOT_EMPTY: "Is Not Empty",
    Operator.EQUALS: "Equals",
    Operator.DOES_NOT_EQUAL: "Does Not Equal",
    Operator.GREATER_THAN: "Greater Than",
    Operator.GREATER_OR_EQUAL: "Greater Than or Equal",
    Operator.LESS_THAN: "Less Than",
    Operator.LESS_OR_EQUAL: "Less Than or Equal",
    Operator.IS_ON: "Is On",
    Operator.IS_BEFORE: "Is Before",
    Operator.IS_AFTER: "Is After",
    Operator.WITHIN_LAST_DAYS: "Within the Last N Days",
    Operator.IS_YES: "Is Yes",
    Operator.IS_NO: "Is No",
}


def _choices(*items: tuple[str, str]) -> tuple[ChoiceDefinition, ...]:
    return tuple(ChoiceDefinition(value, label) for value, label in items)


FIELD_DEFINITIONS = (
    FieldDefinition("package_name", "Package Name", FieldType.TEXT),
    FieldDefinition("play_title", "Play Store Title", FieldType.TEXT),
    FieldDefinition("notes", "Notes", FieldType.TEXT),
    FieldDefinition(
        "criticality_key",
        "Store Status",
        FieldType.CHOICE,
        _choices(
            ("green", "Recent Update"),
            ("yellow", "Aging"),
            ("orange", "Stale"),
            ("red", "Not Found"),
            ("blue", "Store Anomaly"),
            ("purple", "Other / Inconclusive"),
        ),
    ),
    FieldDefinition(
        "play_status",
        "Play Status",
        FieldType.CHOICE,
        _choices(
            ("available", "Available"),
            ("available_in_other_country", "Available in Another Country"),
            ("available_in_fallback_locale_only", "Available in Fallback Locale Only"),
            ("not_found_in_checked_countries", "Not Found in Checked Countries"),
            ("not_found_or_unavailable", "Not Found or Unavailable"),
            ("multi_country_check_inconclusive", "Multi-country Check Inconclusive"),
            ("check_failed", "Check Failed"),
            ("request_error", "Request Error"),
            ("http_error", "HTTP Error"),
            ("unexpected_error", "Unexpected Error"),
            ("cancelled", "Cancelled"),
        ),
    ),
    FieldDefinition(
        "version_comparison",
        "Installed vs Store",
        FieldType.CHOICE,
        _choices(
            ("Match", "Match"),
            ("Outdated", "Outdated"),
            ("Newer", "Newer"),
            ("Different", "Different"),
            ("Device-specific", "Device-specific"),
            ("Unknown", "Unknown"),
        ),
    ),
    FieldDefinition(
        "local_apk_version_comparison",
        "Local APK vs Store",
        FieldType.CHOICE,
        _choices(
            ("N/A", "N/A"),
            ("Match", "Match"),
            ("Outdated", "Outdated"),
            ("Newer", "Newer"),
            ("Different", "Different"),
            ("Device-specific", "Device-specific"),
            ("Unknown", "Unknown"),
        ),
    ),
    FieldDefinition(
        "installer_category",
        "Installer Category",
        FieldType.CHOICE,
        _choices(
            ("google_play", "Google Play"),
            ("alternative_store", "Alternative Store"),
            ("sideloaded", "Sideloaded"),
            ("unknown_or_preinstalled", "Unknown / Preinstalled"),
            ("other_installer", "Other Installer"),
        ),
    ),
    FieldDefinition(
        "compatibility_status",
        "Android Compatibility",
        FieldType.CHOICE,
        _choices(
            ("Modern", "Modern"),
            ("Aging target", "Aging Target"),
            ("Legacy target", "Legacy Target"),
            ("Unknown", "Unknown"),
        ),
    ),
    FieldDefinition(
        "app_enabled",
        "Enabled State",
        FieldType.CHOICE,
        _choices(("Enabled", "Enabled"), ("Disabled", "Disabled"), ("Unknown", "Unknown")),
    ),
    FieldDefinition(
        "device_change",
        "Device App Inventory Change",
        FieldType.CHOICE,
        _choices(
            ("New on device", "New on Device"),
            ("Version changed", "Version Changed"),
            ("Installer changed", "Installer Changed"),
            ("State changed", "Enabled State Changed"),
            ("Same", "Unchanged"),
        ),
    ),
    FieldDefinition("age_days", "Store Age (Days)", FieldType.NUMBER),
    FieldDefinition("target_sdk", "Target SDK", FieldType.NUMBER),
    FieldDefinition("min_sdk", "Min SDK", FieldType.NUMBER),
    FieldDefinition(
        "sensitive_permissions_count", "Sensitive Permissions Count", FieldType.NUMBER
    ),
    FieldDefinition("health_score", "Maintenance Score", FieldType.NUMBER),
    FieldDefinition("play_last_update", "Last Store Update", FieldType.DATE),
    FieldDefinition("first_install_time", "First Installed", FieldType.DATE),
    FieldDefinition("last_local_update", "Last Local Update", FieldType.DATE),
    FieldDefinition("is_system", "System App", FieldType.BOOLEAN),
)
FIELDS_BY_ID = {definition.field_id: definition for definition in FIELD_DEFINITIONS}

_NO_VALUE_OPERATORS = {
    Operator.IS_EMPTY,
    Operator.IS_NOT_EMPTY,
    Operator.IS_YES,
    Operator.IS_NO,
}
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d.%m.%Y",
    "%d %b %Y",
    "%B %d, %Y",
)


class DuplicateQueryNameError(ValueError):
    pass


def field_definition(field_id: str) -> FieldDefinition | None:
    return FIELDS_BY_ID.get(str(field_id or "").strip())


def operators_for_field(field_id: str) -> tuple[Operator, ...]:
    definition = field_definition(field_id)
    return OPERATORS_BY_TYPE.get(definition.field_type, ()) if definition else ()


def _normalise_number(value: object) -> int | float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number != number or number in {float("inf"), float("-inf")}:
        return None
    return int(number) if number.is_integer() else number


def parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    for date_format in _DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date()
        except ValueError:
            continue
    return None


def normalise_condition(value: object) -> SmartCondition | None:
    if isinstance(value, SmartCondition):
        raw_field = value.field
        raw_operator: object = value.operator
        raw_value = value.value
    elif isinstance(value, Mapping):
        raw_field = str(value.get("field") or "")
        raw_operator = value.get("operator")
        raw_value = value.get("value")
    else:
        return None

    definition = field_definition(raw_field)
    if definition is None:
        return None
    try:
        operator = Operator(str(raw_operator or ""))
    except ValueError:
        return None
    if operator not in OPERATORS_BY_TYPE[definition.field_type]:
        return None

    if operator in _NO_VALUE_OPERATORS:
        normalised_value: str | int | float | None = None
    elif definition.field_type == FieldType.TEXT:
        normalised_value = str(raw_value or "").strip()
        if not normalised_value:
            return None
    elif definition.field_type == FieldType.CHOICE:
        wanted = str(raw_value or "").strip().casefold()
        choice_values = {choice.value.casefold(): choice.value for choice in definition.choices}
        normalised_value = choice_values.get(wanted)
        if normalised_value is None:
            return None
    elif definition.field_type == FieldType.NUMBER or operator == Operator.WITHIN_LAST_DAYS:
        normalised_value = _normalise_number(raw_value)
        if normalised_value is None:
            return None
        if operator == Operator.WITHIN_LAST_DAYS and (
            normalised_value < 0 or not isinstance(normalised_value, int)
        ):
            return None
    elif definition.field_type == FieldType.DATE:
        parsed = parse_date(raw_value)
        if parsed is None:
            return None
        normalised_value = parsed.isoformat()
    else:
        return None
    return SmartCondition(definition.field_id, operator, normalised_value)


def _valid_uuid(value: object) -> str | None:
    try:
        return str(UUID(str(value or "")))
    except (ValueError, AttributeError, TypeError):
        return None


def normalise_query(value: object, *, require_name: bool = True) -> SmartQuery | None:
    raw_id: object
    raw_name: object
    raw_match: object
    raw_conditions: object
    schema_version: object
    if isinstance(value, SmartQuery):
        raw_id = value.query_id
        raw_name = value.name
        raw_match = value.match
        raw_conditions = value.conditions
        schema_version = SCHEMA_VERSION
    elif isinstance(value, Mapping):
        raw_id = value.get("id")
        raw_name = value.get("name")
        raw_match = value.get("match")
        raw_conditions = value.get("conditions")
        schema_version = value.get("schema_version")
    else:
        return None

    if schema_version != SCHEMA_VERSION:
        return None
    query_id = _valid_uuid(raw_id)
    if query_id is None:
        return None
    name = " ".join(str(raw_name or "").strip().split())[:MAX_NAME_LENGTH]
    if require_name and not name:
        return None
    try:
        match = MatchMode(str(raw_match or ""))
    except ValueError:
        return None
    if not isinstance(raw_conditions, (list, tuple)):
        return None
    if not 1 <= len(raw_conditions) <= MAX_CONDITIONS:
        return None
    conditions = tuple(normalise_condition(condition) for condition in raw_conditions)
    if any(condition is None for condition in conditions):
        return None
    return SmartQuery(query_id, name, match, tuple(condition for condition in conditions if condition))


def create_query(
    name: str,
    match: MatchMode | str,
    conditions: list[SmartCondition] | tuple[SmartCondition, ...],
    *,
    query_id: str | None = None,
    require_name: bool = True,
) -> SmartQuery | None:
    return normalise_query(
        {
            "schema_version": SCHEMA_VERSION,
            "id": query_id or str(uuid4()),
            "name": name,
            "match": str(match),
            "conditions": list(conditions),
        },
        require_name=require_name,
    )


def query_to_dict(query: SmartQuery) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "id": query.query_id,
        "name": query.name,
        "match": query.match.value,
        "conditions": [
            {
                "field": condition.field,
                "operator": condition.operator.value,
                "value": condition.value,
            }
            for condition in query.conditions
        ],
    }


def _settings_payload(queries: list[SmartQuery]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "items": [query_to_dict(query) for query in queries],
    }


def load_queries() -> list[SmartQuery]:
    stored = state.load_settings().get(SETTINGS_KEY)
    if not isinstance(stored, Mapping) or stored.get("schema_version") != SCHEMA_VERSION:
        return []
    items = stored.get("items")
    if not isinstance(items, list):
        return []

    queries: list[SmartQuery] = []
    names: set[str] = set()
    ids: set[str] = set()
    for item in items:
        query = normalise_query(item)
        if query is None or query.query_id in ids or query.name.casefold() in names:
            continue
        queries.append(query)
        ids.add(query.query_id)
        names.add(query.name.casefold())
    return sorted(queries, key=lambda query: query.name.casefold())


def name_conflict(
    name: str,
    queries: list[SmartQuery] | None = None,
    *,
    exclude_id: str | None = None,
) -> SmartQuery | None:
    wanted = " ".join(str(name or "").strip().split()).casefold()
    for query in queries if queries is not None else load_queries():
        if query.query_id != exclude_id and query.name.casefold() == wanted:
            return query
    return None


def save_query(query: SmartQuery, *, replace_name: bool = False) -> SmartQuery:
    normalised = normalise_query(query)
    if normalised is None:
        raise ValueError("Invalid Smart Query")

    queries = load_queries()
    conflict = name_conflict(normalised.name, queries, exclude_id=normalised.query_id)
    if conflict is not None and not replace_name:
        raise DuplicateQueryNameError(normalised.name)
    if conflict is not None:
        queries = [query for query in queries if query.query_id != conflict.query_id]

    replaced = False
    updated: list[SmartQuery] = []
    for current in queries:
        if current.query_id == normalised.query_id:
            updated.append(normalised)
            replaced = True
        else:
            updated.append(current)
    if not replaced:
        updated.append(normalised)
    updated.sort(key=lambda item: item.name.casefold())

    settings = state.load_settings()
    settings[SETTINGS_KEY] = _settings_payload(updated)
    state.save_settings(settings)
    return normalised


def delete_query(query_id: str) -> bool:
    queries = load_queries()
    remaining = [query for query in queries if query.query_id != query_id]
    if len(remaining) == len(queries):
        return False
    settings = state.load_settings()
    settings[SETTINGS_KEY] = _settings_payload(remaining)
    state.save_settings(settings)
    return True


def _missing(value: object, field_type: FieldType) -> bool:
    if value is None:
        return True
    if field_type == FieldType.NUMBER:
        return _normalise_number(value) is None
    if field_type == FieldType.DATE:
        return parse_date(value) is None
    if field_type == FieldType.BOOLEAN:
        return False
    return not str(value).strip()


def _boolean(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().casefold()
    if text in {"1", "true", "yes", "enabled"}:
        return True
    if text in {"0", "false", "no", "disabled"}:
        return False
    return None


def condition_matches(
    row: Mapping[str, Any],
    condition: SmartCondition,
    *,
    today: date | None = None,
) -> bool:
    definition = FIELDS_BY_ID.get(condition.field)
    if definition is None:
        return False
    raw = row.get(condition.field)
    missing = _missing(raw, definition.field_type)
    operator = condition.operator
    if operator == Operator.IS_EMPTY:
        return missing
    if operator == Operator.IS_NOT_EMPTY:
        return not missing
    if missing:
        return False

    if definition.field_type in {FieldType.TEXT, FieldType.CHOICE}:
        actual = str(raw).strip().casefold()
        wanted = str(condition.value or "").strip().casefold()
        if operator == Operator.CONTAINS:
            return wanted in actual
        if operator == Operator.DOES_NOT_CONTAIN:
            return wanted not in actual
        if operator == Operator.IS:
            return actual == wanted
        if operator == Operator.IS_NOT:
            return actual != wanted
        if operator == Operator.STARTS_WITH:
            return actual.startswith(wanted)
        return False

    if definition.field_type == FieldType.NUMBER:
        actual_number = _normalise_number(raw)
        wanted_number = _normalise_number(condition.value)
        if actual_number is None or wanted_number is None:
            return False
        if operator == Operator.EQUALS:
            return actual_number == wanted_number
        if operator == Operator.DOES_NOT_EQUAL:
            return actual_number != wanted_number
        if operator == Operator.GREATER_THAN:
            return actual_number > wanted_number
        if operator == Operator.GREATER_OR_EQUAL:
            return actual_number >= wanted_number
        if operator == Operator.LESS_THAN:
            return actual_number < wanted_number
        if operator == Operator.LESS_OR_EQUAL:
            return actual_number <= wanted_number
        return False

    if definition.field_type == FieldType.DATE:
        actual_date = parse_date(raw)
        if actual_date is None:
            return False
        if operator == Operator.WITHIN_LAST_DAYS:
            days = _normalise_number(condition.value)
            if not isinstance(days, int) or days < 0:
                return False
            current = today or date.today()
            return current - timedelta(days=days) <= actual_date <= current
        wanted_date = parse_date(condition.value)
        if wanted_date is None:
            return False
        if operator == Operator.IS_ON:
            return actual_date == wanted_date
        if operator == Operator.IS_BEFORE:
            return actual_date < wanted_date
        if operator == Operator.IS_AFTER:
            return actual_date > wanted_date
        return False

    if definition.field_type == FieldType.BOOLEAN:
        actual_boolean = _boolean(raw)
        if actual_boolean is None:
            return False
        return actual_boolean if operator == Operator.IS_YES else not actual_boolean
    return False


def query_matches(
    row: Mapping[str, Any],
    query: SmartQuery | None,
    *,
    today: date | None = None,
) -> bool:
    if query is None:
        return True
    matches = (condition_matches(row, condition, today=today) for condition in query.conditions)
    return all(matches) if query.match == MatchMode.ALL else any(matches)


def renamed_query(query: SmartQuery, name: str) -> SmartQuery | None:
    return normalise_query(replace(query, name=name))


state.DEFAULT_SETTINGS.setdefault(
    SETTINGS_KEY,
    {"schema_version": SCHEMA_VERSION, "items": []},
)

"""Explicit, local Personal Device profile library (schema version 1).

The library contains resolver inputs and safe presentation context only. A record
ID is random and has no relationship to the phone or its profile contents.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType

from playstore_app_audit.platform.runtime import app_data_dir
from playstore_app_audit.services.connected_device_profile import (
    CONNECTED_REQUIRED_FIELDS,
    ConnectedDeviceProfile,
)

SCHEMA_VERSION = 1
PERSONAL_PREFIX = "personal:"
_RECORD_KEYS = frozenset({
    "id", "name", "captured_at", "updated_at", "manufacturer", "model",
    "android_release", "api_level", "cache_revision", "profile",
})


class PersonalDeviceLibraryError(ValueError):
    """Library cannot be safely read or modified."""


@dataclass(frozen=True, slots=True)
class SavedPersonalDeviceProfile:
    profile_id: str
    display_name: str
    captured_at: str
    updated_at: str
    manufacturer: str
    model: str
    android_release: str
    api_level: int
    cache_revision: str
    profile: Mapping[str, str]

    @property
    def profile_hash(self) -> str:
        # The resolver expects a SHA-256 digest. Its saved-profile cache key
        # derives only from independent random local record/revision IDs, never
        # from device or profile contents. Refresh rotates the revision.
        return hashlib.sha256(
            f"personal-cache-v1|{self.profile_id}|{self.cache_revision}".encode()
        ).hexdigest()


def library_path() -> Path:
    try:
        return app_data_dir() / "personal_device_profiles.json"
    except OSError as exc:
        raise PersonalDeviceLibraryError("Personal Device library directory is unavailable.") from exc


def is_personal_profile_id(value: object) -> bool:
    return isinstance(value, str) and value.startswith(PERSONAL_PREFIX)


def _name(value: object) -> str:
    if not isinstance(value, str):
        raise PersonalDeviceLibraryError("Enter a local profile name.")
    name = value.strip()
    if (
        not name or len(name) > 80 or any(ord(char) < 32 for char in name)
        or re.search(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b", name)
    ):
        raise PersonalDeviceLibraryError("Enter a profile name of 1 to 80 printable characters.")
    return name


def _timestamp(value: object) -> str:
    if not isinstance(value, str):
        raise PersonalDeviceLibraryError("Invalid profile timestamp.")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise PersonalDeviceLibraryError("Invalid profile timestamp.") from exc
    if parsed.tzinfo is None:
        raise PersonalDeviceLibraryError("Invalid profile timestamp.")
    return parsed.astimezone(UTC).isoformat()


def _payload(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != CONNECTED_REQUIRED_FIELDS:
        raise PersonalDeviceLibraryError("Incomplete or unapproved Device Specific profile fields.")
    if any(not isinstance(key, str) or not isinstance(item, str) or not item.strip()
           or any(ord(char) < 32 for char in item) for key, item in value.items()):
        raise PersonalDeviceLibraryError("Invalid Device Specific profile value.")
    try:
        if int(value["Build.VERSION.SDK_INT"]) <= 0:
            raise ValueError
    except ValueError as exc:
        raise PersonalDeviceLibraryError("Invalid Android API level.") from exc
    return {key: value[key].strip() for key in sorted(CONNECTED_REQUIRED_FIELDS)}


def _record(raw: object) -> SavedPersonalDeviceProfile:
    if not isinstance(raw, dict) or set(raw) != _RECORD_KEYS:
        raise PersonalDeviceLibraryError("Invalid Personal Device record fields.")
    profile_id = raw["id"]
    _random_uuid(profile_id, prefix=PERSONAL_PREFIX)
    _random_uuid(raw["cache_revision"])
    profile = _payload(raw["profile"])
    manufacturer = profile["Build.MANUFACTURER"]
    model = profile["Build.MODEL"]
    release = profile["Build.VERSION.RELEASE"]
    api = int(profile["Build.VERSION.SDK_INT"])
    if (raw["manufacturer"], raw["model"], raw["android_release"], raw["api_level"]) != (manufacturer, model, release, api):
        raise PersonalDeviceLibraryError("Personal Device context does not match the profile.")
    return SavedPersonalDeviceProfile(
        profile_id, _name(raw["name"]), _timestamp(raw["captured_at"]),
        _timestamp(raw["updated_at"]), manufacturer, model, release, api,
        raw["cache_revision"],
        MappingProxyType(profile),
    )


def _random_uuid(value: object, *, prefix: str = "") -> None:
    if not isinstance(value, str) or not value.startswith(prefix):
        raise PersonalDeviceLibraryError("Invalid random library identifier.")
    raw = value[len(prefix):]
    try:
        parsed = uuid.UUID(raw)
    except ValueError as exc:
        raise PersonalDeviceLibraryError("Invalid random library identifier.") from exc
    if parsed.version != 4 or str(parsed) != raw:
        raise PersonalDeviceLibraryError("Invalid random library identifier.")


def _document(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "profiles": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PersonalDeviceLibraryError("Personal Device library cannot be read.") from exc
    if not isinstance(data, dict) or set(data) != {"schema_version", "profiles"} or not isinstance(data["profiles"], list):
        raise PersonalDeviceLibraryError("Invalid Personal Device library structure.")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise PersonalDeviceLibraryError("Unsupported Personal Device library schema; file preserved.")
    return data


def list_profiles(*, path: Path | None = None) -> tuple[SavedPersonalDeviceProfile, ...]:
    records = _document(path or library_path())["profiles"]
    valid: list[SavedPersonalDeviceProfile] = []
    seen: set[str] = set()
    for raw in records:
        try:
            profile = _record(raw)
        except PersonalDeviceLibraryError:
            continue
        if profile.profile_id not in seen:
            valid.append(profile)
            seen.add(profile.profile_id)
    return tuple(valid)


def get_profile(profile_id: str, *, path: Path | None = None) -> SavedPersonalDeviceProfile:
    return next((profile for profile in list_profiles(path=path) if profile.profile_id == profile_id), None) or _missing()


def _missing() -> SavedPersonalDeviceProfile:
    raise KeyError("Saved Personal Device profile is unavailable.")


def _write(path: Path, records: list[dict[str, object]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp.write_text(json.dumps({"schema_version": SCHEMA_VERSION, "profiles": records}, indent=2, ensure_ascii=False), encoding="utf-8")
        temp.replace(path)
    except OSError as exc:
        with suppress(OSError):
            temp.unlink(missing_ok=True)
        raise PersonalDeviceLibraryError("Personal Device library could not be saved.") from exc


def _editable(path: Path) -> list[dict[str, object]]:
    records = _document(path)["profiles"]
    try:
        parsed = [_record(raw) for raw in records]
    except PersonalDeviceLibraryError as exc:
        raise PersonalDeviceLibraryError("Library has a malformed record; repair it before changing profiles.") from exc
    if len({profile.profile_id for profile in parsed}) != len(parsed):
        raise PersonalDeviceLibraryError("Library contains duplicate record IDs.")
    return records


def _from_capture(capture: ConnectedDeviceProfile, name: str, profile_id: str, captured_at: str) -> dict[str, object]:
    if not isinstance(capture, ConnectedDeviceProfile) or not capture.complete:
        raise PersonalDeviceLibraryError("Capture is incomplete for Device Specific use.")
    profile = _payload(dict(capture.profile))
    now = datetime.now(UTC).isoformat()
    return {
        "id": profile_id, "name": _name(name), "captured_at": captured_at,
        "cache_revision": str(uuid.uuid4()),
        "updated_at": now, "manufacturer": profile["Build.MANUFACTURER"],
        "model": profile["Build.MODEL"], "android_release": profile["Build.VERSION.RELEASE"],
        "api_level": int(profile["Build.VERSION.SDK_INT"]), "profile": profile,
    }


def save_capture(capture: ConnectedDeviceProfile, name: str, *, path: Path | None = None) -> SavedPersonalDeviceProfile:
    target = path or library_path()
    records = _editable(target)
    now = datetime.now(UTC).isoformat()
    record = _from_capture(capture, name, f"{PERSONAL_PREFIX}{uuid.uuid4()}", now)
    records.append(record)
    _write(target, records)
    return _record(record)


def rename_profile(profile_id: str, name: str, *, path: Path | None = None) -> SavedPersonalDeviceProfile:
    target = path or library_path()
    records = _editable(target)
    record = next((item for item in records if item["id"] == profile_id), None)
    if record is None:
        return _missing()
    record["name"] = _name(name)
    _write(target, records)
    return _record(record)


def delete_profile(profile_id: str, *, path: Path | None = None) -> None:
    target = path or library_path()
    records = _editable(target)
    retained = [item for item in records if item["id"] != profile_id]
    if len(retained) == len(records):
        _missing()
    _write(target, retained)


def refresh_compatibility(saved: SavedPersonalDeviceProfile, capture: ConnectedDeviceProfile) -> bool:
    """Reject obvious model mismatches; matching context cannot prove identity."""
    return (
        capture.complete
        and str(capture.profile.get("Build.MANUFACTURER", "")).casefold() == saved.manufacturer.casefold()
        and str(capture.profile.get("Build.MODEL", "")).casefold() == saved.model.casefold()
    )


def refresh_profile(profile_id: str, capture: ConnectedDeviceProfile, *, path: Path | None = None) -> SavedPersonalDeviceProfile:
    target = path or library_path()
    records = _editable(target)
    index = next((index for index, item in enumerate(records) if item["id"] == profile_id), None)
    if index is None:
        return _missing()
    saved = _record(records[index])
    if not refresh_compatibility(saved, capture):
        raise PersonalDeviceLibraryError("The connected phone has a different manufacturer or model.")
    records[index] = _from_capture(capture, saved.display_name, profile_id, saved.captured_at)
    _write(target, records)
    return _record(records[index])

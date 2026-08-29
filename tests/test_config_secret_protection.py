from __future__ import annotations

import json

import pytest

import playstore_app_audit.platform.machine_identity as machine_identity
import playstore_app_audit.services.alternative_distribution as alternative
import playstore_app_audit.services.config_secret_protection as secrets
import playstore_app_audit.services.state as state

SYNTHETIC_KEY = "synthetic-test-api-key-G4-12345"


@pytest.fixture(autouse=True)
def stable_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets, "local_machine_identity", lambda: "machine-a")
    monkeypatch.setattr(secrets, "local_user_identity", lambda: "user-a")


def test_secret_round_trip_and_envelope_never_contains_plaintext() -> None:
    protected = secrets.protect_secret(SYNTHETIC_KEY)

    result = secrets.unprotect_secret(protected)

    assert protected.startswith("v1:")
    assert SYNTHETIC_KEY not in protected
    assert result.available
    assert result.value == SYNTHETIC_KEY
    assert SYNTHETIC_KEY not in repr(result)


def test_saved_settings_contain_only_protected_credential(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(state, "settings_path", lambda: settings_file)
    configured = alternative.replace_aptoide_credential(state.load_settings(), SYNTHETIC_KEY)

    state.save_settings(configured)

    serialized = settings_file.read_text(encoding="utf-8")
    assert SYNTHETIC_KEY not in serialized
    assert "api_key_protected" in serialized
    assert json.loads(serialized)["alternative_distribution"]["aptoide"][
        "api_key_protected"
    ].startswith("v1:")


def test_changed_machine_or_user_identity_fails_without_plaintext_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    protected = secrets.protect_secret(SYNTHETIC_KEY)
    monkeypatch.setattr(secrets, "local_machine_identity", lambda: "machine-b")

    result = secrets.unprotect_secret(protected)

    assert not result.available
    assert result.value == ""
    assert "cannot be used on this device" in result.message
    assert SYNTHETIC_KEY not in repr(result)


def test_tamper_malformed_and_unsupported_envelopes_fail_safely() -> None:
    protected = secrets.protect_secret(SYNTHETIC_KEY)
    final = "A" if protected[-1] != "A" else "B"

    for envelope in (protected[:-1] + final, "not-an-envelope", "v2:YWJj", "v1:!!"):
        result = secrets.unprotect_secret(envelope)
        assert not result.available
        assert result.value == ""


def test_empty_replace_and_remove_credential() -> None:
    assert secrets.protect_secret("") == ""
    assert not secrets.unprotect_secret("").available
    settings = state.load_settings()

    replaced = alternative.replace_aptoide_credential(settings, SYNTHETIC_KEY)
    credential = alternative.aptoide_credential(replaced)
    removed = alternative.remove_aptoide_credential(replaced)

    assert credential.available and credential.value == SYNTHETIC_KEY
    assert removed["alternative_distribution"]["aptoide"]["api_key_protected"] == ""
    assert removed["alternative_distribution"]["aptoide"]["enabled"] is False


def test_credential_bearing_provider_repr_is_redacted() -> None:
    provider = alternative.AptoideProvider("synthetic-store", SYNTHETIC_KEY)

    assert SYNTHETIC_KEY not in repr(provider)


@pytest.mark.parametrize(
    ("system", "source", "value"),
    [
        ("Windows", "windows-machine-guid", "windows-guid"),
        ("Linux", "linux-machine-id", "linux-id"),
        ("Darwin", "macos-platform-uuid", "mac-uuid"),
    ],
)
def test_machine_identity_prefers_platform_source(
    monkeypatch: pytest.MonkeyPatch, system: str, source: str, value: str
) -> None:
    monkeypatch.setattr(machine_identity.platform, "system", lambda: system)
    monkeypatch.setattr(machine_identity, "_windows_machine_guid", lambda: "windows-guid")
    monkeypatch.setattr(machine_identity, "_linux_machine_id", lambda: "linux-id")
    monkeypatch.setattr(machine_identity, "_macos_platform_uuid", lambda: "mac-uuid")

    assert machine_identity._preferred_machine_id() == (source, value)


def test_machine_identity_fallback_is_deterministic_and_raw_details_are_not_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(machine_identity.platform, "system", lambda: "Unknown")
    monkeypatch.setattr(machine_identity.socket, "gethostname", lambda: "synthetic-host")
    monkeypatch.setattr(machine_identity.getpass, "getuser", lambda: "synthetic-user")
    monkeypatch.setattr(machine_identity.uuid, "getnode", lambda: 1234)

    first = machine_identity.local_machine_identity()
    second = machine_identity.local_machine_identity()

    assert first == second
    assert "synthetic-host" not in first
    assert "synthetic-user" not in first

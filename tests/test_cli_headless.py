from __future__ import annotations

import csv
import json
import subprocess
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from playstore_app_audit import cli
from playstore_app_audit.services import app_list_system, headless_audit, result_csv, result_json, state


def _settings() -> dict[str, object]:
    return {
        **state.DEFAULT_SETTINGS,
        "cache_enabled": False,
        "alternative_distribution": {"fdroid_main": {"enabled": False}},
    }


def _store_row(package: str, status: str = "available") -> dict[str, object]:
    return {
        "app_name": package,
        "package_name": package,
        "play_status": status,
        "play_last_update": "2026-01-01" if status == "available" else "",
        "play_version": "1.0",
    }


def test_parser_source_and_option_contract(tmp_path: Path) -> None:
    parser = cli.build_parser()
    source = tmp_path / "apps.txt"
    for command, expected in (
        (["app-list", str(source)], "app-list"),
        (["apk-files", "one.apk", "two.xapk"], "apk-files"),
        (["apk-folder", str(tmp_path)], "apk-folder"),
        (["phone", "--include-system"], "phone"),
    ):
        assert parser.parse_args(["audit", *command]).source == expected
    options = parser.parse_args([
        "audit", "app-list", str(source), "--country", "it", "--language", "it",
        "--workers", "4", "--fresh", "--format", "csv", "--output", "out.csv",
        "--force", "--device-provider", "custom_dispenser",
        "--device-profile", "android10_api29_oneplus8pro",
        "--device-endpoint", "https://example.com/resolve",
    ])
    assert (options.country, options.language, options.workers, options.fresh) == ("it", "it", 4, True)
    assert (options.format, options.force, options.device_provider) == ("csv", True, "custom_dispenser")
    for invalid in (["audit"], ["audit", "phone", "--include-system", "--include-system", "extra"]):
        with pytest.raises(SystemExit) as error:
            parser.parse_args(invalid)
        assert error.value.code == 2
    with pytest.raises(SystemExit) as help_exit:
        parser.parse_args(["--help"])
    assert help_exit.value.code == 0


def test_app_list_uses_canonical_store_and_versioned_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "apps.csv"
    source.write_text("package_name\ncom.example.first\ncom.example.second\n", encoding="utf-8")
    audited: list[str] = []

    def audit(_self: object, apps: list[dict[str, str]], _config: object, **_kwargs: object) -> list[dict[str, object]]:
        audited.extend(app["package_name"] for app in apps)
        return [_store_row(app["package_name"], "not_found_in_checked_countries") for app in apps]

    monkeypatch.setattr(headless_audit.PlayStoreService, "audit", audit)
    monkeypatch.setattr(headless_audit.alternative_distribution, "run_alternative_distribution_phase", lambda *_a, **_k: [])
    monkeypatch.setattr(headless_audit.device_specific_integration, "enrich_rows_with_device_specific_resolution", lambda *_a, **_k: None)
    rows, context = headless_audit.run_audit(
        headless_audit.AuditSource("app_list", path=source), _settings(), threading.Event(),
        country="it", language="it", workers=2,
    )
    assert audited == ["com.example.first", "com.example.second"]
    assert all(row["criticality_key"] == "red" for row in rows)
    document = result_json.build_results_document(rows, context=context)
    assert document["format"] == result_json.FORMAT_ID
    assert document["schema_version"] == result_json.SCHEMA_VERSION
    assert document["result_count"] == 2


def test_app_list_system_flags_use_shared_gui_service(tmp_path: Path) -> None:
    source = tmp_path / "apps.csv"
    source.write_text(
        "package_name,is_system\ncom.android.settings,yes\ncom.example.user,no\n",
        encoding="utf-8",
    )
    apps = [
        {"package_name": "com.android.settings"},
        {"package_name": "com.example.user"},
    ]
    metadata = app_list_system.read_system_metadata(source, apps)
    assert metadata == {"com.android.settings": True, "com.example.user": False}
    assert app_list_system.classify_packages(apps, metadata) == {"com.android.settings"}


def test_local_files_and_folder_use_fanout_and_hide_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.touch()
    second.touch()
    artifact = SimpleNamespace(package_lookup_key="com.example.same")
    monkeypatch.setattr(headless_audit.local_package_metadata_cache, "parse_cached_local_package", lambda *_a, **_k: (SimpleNamespace(artifact=artifact), False))
    calls: list[int] = []

    def collect(_self: object, artifacts: list[object], *_a: object, **_k: object) -> object:
        calls.append(len(artifacts))
        return SimpleNamespace(
            associations=tuple(SimpleNamespace(artifact=item) for item in artifacts),
            packages=("com.example.same",),
        )

    monkeypatch.setattr(headless_audit.LocalArtifactStoreService, "collect", collect)
    monkeypatch.setattr(headless_audit.local_apk_audit, "association_result_rows", lambda associations: [
        {**_store_row("com.example.same"), "source_mode": "local_apk", "local_apk_location": str(first),
         "local_apk_version_comparison": "Match"} for _ in associations
    ])
    for source in (
        headless_audit.AuditSource("local_files", files=(first, second)),
        headless_audit.AuditSource("local_folder", path=tmp_path),
    ):
        rows, context = headless_audit.run_audit(source, _settings(), threading.Event())
        assert len(rows) == 2
        assert context["packages"] == 1
        assert rows[0]["local_apk_version_comparison"] == "Match"
        assert "local_apk_location" not in result_json.build_results_document(rows)["results"][0]
    assert calls == [2, 2]


def test_invalid_local_package_uses_parser_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "broken.apk"
    path.write_bytes(b"not an APK")
    monkeypatch.setattr(headless_audit.local_package_metadata_cache, "parse_cached_local_package", lambda *_a, **_k: (SimpleNamespace(artifact=None, failure=object()), False))
    with pytest.raises(headless_audit.InvalidAuditInput):
        headless_audit.run_audit(
            headless_audit.AuditSource("local_files", files=(path,)), _settings(), threading.Event()
        )


def test_phone_uses_scan_session_without_exporting_serial(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[bool] = []
    session = SimpleNamespace(
        packages=("com.example.phone",), locale=None,
        full_metadata_status=headless_audit.scan_session.FullMetadataStatus.NOT_REQUESTED,
        device_id="internal-hash", manufacturer="Acme", model="X", android_version="14",
        android_api="34", package_count=1, system_package_count=0,
    )
    monkeypatch.setattr(headless_audit, "find_adb", lambda: "adb")

    def collect(_adb: str, *, exclude_system: bool, **_kwargs: object) -> object:
        captured.append(exclude_system)
        return session

    monkeypatch.setattr(headless_audit.scan_session, "collect_scan_session", collect)
    monkeypatch.setattr(headless_audit, "_store_rows", lambda apps, *_a, **_k: [_store_row(apps[0]["package_name"])])
    monkeypatch.setattr(headless_audit.device_insights, "collect_device_metadata_v9", lambda *_a: {})
    monkeypatch.setattr(headless_audit.scan_session, "authorised_device_matches", lambda *_a: True)
    monkeypatch.setattr(headless_audit.scan_session, "enrich_rows_with_compact_metadata", lambda *_a: None)
    monkeypatch.setattr(headless_audit.device_specific_integration, "enrich_rows_with_device_specific_resolution", lambda *_a, **_k: None)
    monkeypatch.setattr(headless_audit.alternative_distribution, "run_alternative_distribution_phase", lambda *_a, **_k: [])
    rows, context = headless_audit.run_audit(
        headless_audit.AuditSource("phone", include_system=True), _settings(), threading.Event()
    )
    assert captured == [False]
    assert rows[0]["package_name"] == "com.example.phone"
    assert "internal-hash" not in json.dumps(result_json.build_results_document(rows, context=context))


def test_phone_scan_cancellation_reaches_collector(monkeypatch: pytest.MonkeyPatch) -> None:
    cancelled = threading.Event()
    monkeypatch.setattr(headless_audit, "find_adb", lambda: "adb")

    def collect(_adb: str, *, cancel_event: threading.Event, **_kwargs: object) -> object:
        assert cancel_event is cancelled
        cancel_event.set()
        return SimpleNamespace(locale=None)

    monkeypatch.setattr(headless_audit.scan_session, "collect_scan_session", collect)
    rows, context = headless_audit.run_audit(
        headless_audit.AuditSource("phone"), _settings(), cancelled
    )
    assert rows == [] and context == {}


def test_device_specific_builtin_saved_and_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _settings()
    settings["device_specific_provider"] = "custom_dispenser"
    settings["device_specific_resolver_endpoint"] = "https://example.com/resolve"
    settings["device_specific_resolver_profile"] = "android10_api29_oneplus8pro"
    headless_audit.validate_device_specific(settings, headless_audit.AuditSource("app_list"))
    saved_id = "personal:11111111-1111-4111-8111-111111111111"
    settings["device_specific_resolver_profile"] = saved_id
    monkeypatch.setattr(headless_audit.personal_device_library, "get_profile", lambda _id: object())
    headless_audit.validate_device_specific(settings, headless_audit.AuditSource("app_list"))
    exported = result_json.build_results_document([{
        **_store_row("com.example.app"), "device_specific_profile_id": saved_id,
    }])["results"][0]
    assert exported["device_specific_profile_id"] == "personal_device"

    def missing(_id: str) -> object:
        raise KeyError("secret")

    monkeypatch.setattr(headless_audit.personal_device_library, "get_profile", missing)
    with pytest.raises(headless_audit.InvalidAuditInput):
        headless_audit.validate_device_specific(settings, headless_audit.AuditSource("app_list"))


@pytest.mark.parametrize("play_version", ["1.0", "Varies with device"])
def test_inherited_expired_personal_session_does_not_block_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], play_version: str,
) -> None:
    source = tmp_path / "apps.txt"
    source.write_text("com.example.app\n", encoding="utf-8")
    settings = _settings()
    settings["device_specific_provider"] = "personal_google_session"
    settings["private_marker"] = "secret-session-material"
    monkeypatch.setattr(cli.state, "load_settings", lambda **_k: dict(settings))
    monkeypatch.setattr(headless_audit.PlayStoreService, "audit", lambda _self, _apps, _config, **_k: [
        {**_store_row("com.example.app"), "play_version": play_version}
    ])
    monkeypatch.setattr(headless_audit.alternative_distribution, "run_alternative_distribution_phase", lambda *_a, **_k: [])
    monkeypatch.setattr(
        headless_audit.device_specific_integration.device_specific_personal_session,
        "personal_session_status", lambda: SimpleNamespace(signed_in=False, context_hash=""),
    )

    assert cli.main(["audit", "app-list", str(source), "--country", "it"]) == 0
    output = capsys.readouterr().out
    assert "secret-session-material" not in output
    document = json.loads(output)
    assert document["results"][0]["play_version"] == play_version
    assert document["results"][0]["play_status"] == "available"


@pytest.mark.parametrize("profile_id", [
    "personal:11111111-1111-4111-8111-111111111111", "connected_device",
])
def test_inherited_unavailable_profile_is_optional_for_app_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], profile_id: str,
) -> None:
    source = tmp_path / "apps.txt"
    source.write_text("com.example.app\n", encoding="utf-8")
    settings = _settings()
    settings["device_specific_provider"] = "custom_dispenser"
    settings["device_specific_resolver_profile"] = profile_id
    settings["device_specific_resolver_endpoint"] = "https://example.com/resolve"
    monkeypatch.setattr(cli.state, "load_settings", lambda **_k: dict(settings))
    monkeypatch.setattr(headless_audit.PlayStoreService, "audit", lambda _self, _apps, _config, **_k: [
        {**_store_row("com.example.app"), "play_version": "Varies with device"}
    ])
    monkeypatch.setattr(headless_audit.alternative_distribution, "run_alternative_distribution_phase", lambda *_a, **_k: [])
    if profile_id.startswith("personal:"):
        monkeypatch.setattr(headless_audit.personal_device_library, "get_profile", lambda _id: (_ for _ in ()).throw(KeyError("missing")))

    assert cli.main(["audit", "app-list", str(source), "--country", "it"]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["play_status"] == "available"
    assert settings["device_specific_resolver_profile"] == profile_id


@pytest.mark.parametrize("overrides", [
    ["--device-provider", "custom_dispenser", "--device-profile", "unknown"],
    ["--device-provider", "custom_dispenser", "--device-endpoint", "http://invalid"],
    ["--device-provider", "personal_google_session", "--device-endpoint", "https://example.com/resolve"],
    ["--device-provider", "custom_dispenser", "--device-profile", "connected_device"],
])
def test_explicit_invalid_device_options_exit_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, overrides: list[str],
) -> None:
    source = tmp_path / "apps.txt"
    source.write_text("com.example.app\n", encoding="utf-8")
    monkeypatch.setattr(cli.state, "load_settings", lambda **_k: _settings())
    monkeypatch.setattr(headless_audit.PlayStoreService, "audit", lambda *_a, **_k: pytest.fail("Store audit should not run"))
    assert cli.main(["audit", "app-list", str(source), *overrides]) == 2


def test_explicit_valid_device_options_run_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = tmp_path / "apps.txt"
    source.write_text("com.example.app\n", encoding="utf-8")
    monkeypatch.setattr(cli.state, "load_settings", lambda **_k: _settings())
    monkeypatch.setattr(headless_audit.PlayStoreService, "audit", lambda *_a, **_k: [_store_row("com.example.app")])
    monkeypatch.setattr(headless_audit.alternative_distribution, "run_alternative_distribution_phase", lambda *_a, **_k: [])
    assert cli.main([
        "audit", "app-list", str(source), "--device-provider", "custom_dispenser",
        "--device-profile", "android10_api29_oneplus8pro",
        "--device-endpoint", "https://example.com/resolve",
    ]) == 0
    assert json.loads(capsys.readouterr().out)["results"][0]["package_name"] == "com.example.app"


def test_fresh_bypasses_only_result_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    cached_calls: list[int] = []
    store_calls: list[int] = []

    def cache(_apps: object, _country: str, _language: str, _ttl: int) -> dict[str, dict[str, object]]:
        cached_calls.append(1)
        return {"com.example.app": _store_row("com.example.app")}

    def audit(_self: object, apps: list[dict[str, str]], _config: object, **_kwargs: object) -> list[dict[str, object]]:
        store_calls.append(len(apps))
        return [_store_row(app["package_name"]) for app in apps]

    monkeypatch.setattr(headless_audit.state, "load_fresh_cache", cache)
    monkeypatch.setattr(headless_audit.state, "update_cache", lambda *_a: None)
    monkeypatch.setattr(headless_audit.PlayStoreService, "audit", audit)
    monkeypatch.setattr(headless_audit.device_specific_integration, "enrich_rows_with_device_specific_resolution", lambda *_a, **_k: None)
    monkeypatch.setattr(headless_audit.alternative_distribution, "run_alternative_distribution_phase", lambda *_a, **_k: [])
    settings = _settings()
    settings["cache_enabled"] = True
    apps = [{"app_name": "App", "package_name": "com.example.app"}]
    config = headless_audit.AuditConfig(country="it", language="it")
    headless_audit._store_rows(apps, config, settings, threading.Event(), None, fresh=False)
    headless_audit._store_rows(apps, config, settings, threading.Event(), None, fresh=True)
    assert cached_calls == [1]
    assert store_calls == [1]


def test_cli_settings_read_does_not_persist_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "settings.json"
    original = '{"store_language": "en", "cache_ttl_hours": 72}'
    path.write_text(original, encoding="utf-8")
    monkeypatch.setattr(state, "settings_path", lambda: path)
    settings = state.load_settings(persist_migrations=False)
    assert settings["store_language"] == "auto"
    assert path.read_text(encoding="utf-8") == original


def test_cli_overrides_are_command_local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "apps.txt"
    source.write_text("com.example.app\n", encoding="utf-8")
    saved = _settings()
    saved["store_language"] = "en"
    captured: dict[str, object] = {}
    monkeypatch.setattr(cli.state, "load_settings", lambda **_k: dict(saved))

    def run(_source: object, settings: dict[str, object], _cancelled: object, **kwargs: object) -> tuple[list[object], dict[str, object]]:
        captured.update({"settings": settings, **kwargs})
        return [], {"source_mode": "file"}

    monkeypatch.setattr(cli, "run_audit", run)
    assert cli.main([
        "audit", "app-list", str(source), "--country", "it", "--language", "it",
        "--workers", "2", "--fresh", "--device-provider", "disabled",
    ]) == 0
    assert (captured["country"], captured["language"], captured["workers"], captured["fresh"]) == ("it", "it", 2, True)
    assert saved["store_language"] == "en"
    assert saved["device_specific_provider"] == "disabled"


def test_output_atomicity_overwrite_and_csv_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "input.txt"
    source.write_text("com.example.app\n", encoding="utf-8")
    output = tmp_path / "result.json"
    monkeypatch.setattr(cli.state, "load_settings", lambda **_k: _settings())
    monkeypatch.setattr(cli, "run_audit", lambda *_a, **_k: ([_store_row("com.example.app")], {"source_mode": "file"}))
    command = ["audit", "app-list", str(source), "--output", str(output)]
    assert cli.main(command) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == result_json.SCHEMA_VERSION
    assert cli.main(command) == 2
    assert cli.main([*command, "--force"]) == 0
    assert not list(tmp_path.glob("*.tmp"))
    assert cli.main(["audit", "app-list", str(source), "--output", str(source), "--force"]) == 2
    csv_output = tmp_path / "result.csv"
    assert cli.main(["audit", "app-list", str(source), "--format", "csv", "--output", str(csv_output)]) == 0
    with csv_output.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == result_csv.EXPORT_FIELDS
        assert next(reader)["package_name"] == "com.example.app"
    assert cli.main(["audit", "app-list", str(source), "--force"]) == 2


def test_exit_codes_and_no_final_file_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "input.txt"
    source.write_text("com.example.app\n", encoding="utf-8")
    output = tmp_path / "out.json"
    monkeypatch.setattr(cli.state, "load_settings", lambda **_k: _settings())
    command = ["audit", "app-list", str(source), "--output", str(output)]
    monkeypatch.setattr(cli, "run_audit", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("secret-token")))
    assert cli.main(command) == 3
    assert not output.exists()
    assert "secret-token" not in capsys.readouterr().err

    def cancelled(_source: object, _settings: object, event: threading.Event, **_kwargs: object) -> tuple[list[object], dict[str, object]]:
        event.set()
        return [], {}

    monkeypatch.setattr(cli, "run_audit", cancelled)
    assert cli.main(command) == 130
    assert not output.exists()


def test_cancellation_during_serialization_keeps_final_file_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "result.json"
    cancelled = threading.Event()

    def render(_rows: object, _context: object, _settings: object, _format: str, handle: object) -> None:
        handle.write("partial")
        cancelled.set()

    monkeypatch.setattr(cli, "_render", render)
    with pytest.raises(InterruptedError):
        cli._write_output(output, [], {}, {}, "json", force=False, cancel_event=cancelled)
    assert not output.exists()
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_import_graph_is_headless() -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import sys, playstore_app_audit.cli; "
         "assert not any(name.startswith('playstore_app_audit.ui') for name in sys.modules); "
         "assert 'PySide6' not in sys.modules"],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_source_binary_entry_dispatches_cli_without_qt() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-c",
         "import runpy, sys; sys.argv=['main.py', 'cli', 'audit', '--help']\n"
         "try:\n runpy.run_path('main.py', run_name='__main__')\n"
         "except SystemExit as exc:\n assert exc.code == 0\n"
         "assert 'PySide6' not in sys.modules; "
         "assert not any(name.startswith('playstore_app_audit.ui') for name in sys.modules)"],
        cwd=root, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "app-list" in result.stdout


def test_all_standalone_builds_expose_the_dispatcher() -> None:
    root = Path(__file__).resolve().parents[1]
    windows = (root / ".github/scripts/build_windows_standalone.ps1").read_text(encoding="utf-8")
    windows_validator = (root / ".github/scripts/validate_windows_standalone.py").read_text(encoding="utf-8")
    linux = (root / ".github/workflows/build-linux.yml").read_text(encoding="utf-8")
    macos = (root / ".github/workflows/build-macos.yml").read_text(encoding="utf-8")
    assert '"--windows-console-mode=attach"' in windows
    assert '$NuitkaArgs += "main.py"' in windows
    assert '-ArgumentList @("cli", "audit", "--help")' in windows
    assert '$CliProcess.ExitCode -ne 0' in windows
    assert 'root / "PlayStoreAppAudit.exe"' in windows_validator
    assert 'pyside6-deploy main.py' in linux
    assert '"$ROUNDTRIP_BIN" cli audit --help' in linux
    assert 'pyside6-deploy main.py' in macos
    assert '"$REXEC" cli audit --help' in macos

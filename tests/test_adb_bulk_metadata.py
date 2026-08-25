from __future__ import annotations

import threading

import playstore_app_audit.services.device_insights as insights

BULK_DUMP = """Packages:
  Package [com.example.one] (abc123):
    versionCode=101 minSdk=26 targetSdk=35
    versionName=1.0.1
    firstInstallTime=2026-01-01 10:00:00
    lastUpdateTime=2026-08-01 11:00:00
    requested permissions:
      android.permission.CAMERA
  Package [com.example.two] (def456):
    versionCode=202 minSdk=24 targetSdk=32
    versionName=2.0.2
    firstInstallTime=2025-01-01 10:00:00
    lastUpdateTime=2026-07-01 11:00:00

Queries:
  system apps query data
"""


def test_extract_bulk_package_blocks_is_scoped_to_packages_section() -> None:
    blocks = insights._extract_bulk_package_blocks(BULK_DUMP, {"com.example.one", "com.example.two"})
    assert set(blocks) == {"com.example.one", "com.example.two"}
    assert "versionCode=101" in blocks["com.example.one"]
    assert "Queries:" not in blocks["com.example.two"]


def test_bulk_metadata_avoids_per_package_dumpsys(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(insights.state, "load_settings", lambda: {"permissions_audit_enabled": True})

    def fake_run(adb: str, args: list[str], timeout: int = 30) -> str:
        calls.append(tuple(args))
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args == ["shell", "pm", "list", "packages", "-d"]:
            return "package:com.example.two\n"
        if args == ["shell", "pm", "list", "packages", "-i"]:
            return (
                "package:com.example.one installer=com.android.vending\n"
                "package:com.example.two installer=com.android.vending\n"
            )
        if args == ["shell", "dumpsys", "package"]:
            return BULK_DUMP
        raise AssertionError(f"Unexpected adb call: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)
    result = insights.collect_device_metadata_v9("adb", ["com.example.one", "com.example.two"], max_workers=2)

    assert result["com.example.one"]["installed_version"] == "1.0.1"
    assert result["com.example.one"]["sensitive_permissions_count"] == "1"
    assert result["com.example.one"]["installer_source"].startswith("Google Play")
    assert result["com.example.two"]["app_enabled"] == "Disabled"
    assert result["com.example.two"]["compatibility_status"] == "Aging target"
    assert not [call for call in calls if len(call) == 4 and call[:3] == ("shell", "dumpsys", "package")]


def test_partial_bulk_dump_falls_back_only_for_missing_package(monkeypatch) -> None:
    calls: list[tuple[str, ...]] = []
    one_only = BULK_DUMP.replace(
        "  Package [com.example.two] (def456):\n"
        "    versionCode=202 minSdk=24 targetSdk=32\n"
        "    versionName=2.0.2\n"
        "    firstInstallTime=2025-01-01 10:00:00\n"
        "    lastUpdateTime=2026-07-01 11:00:00\n",
        "",
    )
    monkeypatch.setattr(insights.state, "load_settings", lambda: {"permissions_audit_enabled": False})

    def fake_run(adb: str, args: list[str], timeout: int = 30) -> str:
        calls.append(tuple(args))
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args == ["shell", "pm", "list", "packages", "-d"]:
            return ""
        if args == ["shell", "pm", "list", "packages", "-i"]:
            return ""
        if args == ["shell", "dumpsys", "package"]:
            return one_only
        if args == ["shell", "dumpsys", "package", "com.example.two"]:
            return "versionCode=303 minSdk=24 targetSdk=34\nversionName=3.0.3\n"
        if args == ["shell", "dumpsys", "package", "com.example.one"]:
            raise AssertionError("Bulk-covered package should not be queried again")
        raise AssertionError(f"Unexpected adb call: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)
    result = insights.collect_device_metadata_v9("adb", ["com.example.one", "com.example.two"], max_workers=2)

    assert result["com.example.one"]["installed_version_code"] == "101"
    assert result["com.example.two"]["installed_version"] == "3.0.3"
    specific = [call for call in calls if len(call) == 4 and call[:3] == ("shell", "dumpsys", "package")]
    assert specific == [("shell", "dumpsys", "package", "com.example.two")]


def test_bulk_failure_preserves_per_package_fallback(monkeypatch) -> None:
    monkeypatch.setattr(insights.state, "load_settings", lambda: {"permissions_audit_enabled": False})
    per_package: list[str] = []

    def fake_run(adb: str, args: list[str], timeout: int = 30) -> str:
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args in (
            ["shell", "pm", "list", "packages", "-d"],
            ["shell", "pm", "list", "packages", "-i"],
        ):
            return ""
        if args == ["shell", "dumpsys", "package"]:
            raise RuntimeError("OEM bulk dump unavailable")
        if len(args) == 4 and args[:3] == ["shell", "dumpsys", "package"]:
            per_package.append(args[3])
            return f"versionCode=1 minSdk=23 targetSdk=35\nversionName={args[3]}\n"
        raise AssertionError(f"Unexpected adb call: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)
    result = insights.collect_device_metadata_v9("adb", ["pkg.one", "pkg.two"], max_workers=2)
    assert set(result) == {"pkg.one", "pkg.two"}
    assert set(per_package) == {"pkg.one", "pkg.two"}


def test_stop_drains_only_in_flight_per_package_fallback(monkeypatch) -> None:
    packages = [f"pkg.{index}" for index in range(5)]
    cancel_event = threading.Event()
    in_flight_started = threading.Event()
    release_in_flight = threading.Event()
    lock = threading.Lock()
    per_package: list[str] = []
    monkeypatch.setattr(insights.state, "load_settings", lambda: {"permissions_audit_enabled": False})

    def fake_run(adb: str, args: list[str], timeout: int = 30) -> str:
        del adb, timeout
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args in (
            ["shell", "pm", "list", "packages", "-d"],
            ["shell", "pm", "list", "packages", "-i"],
        ):
            return ""
        if args == ["shell", "dumpsys", "package"]:
            raise RuntimeError("force per-package fallback")
        if len(args) == 4 and args[:3] == ["shell", "dumpsys", "package"]:
            with lock:
                per_package.append(args[3])
                if len(per_package) == 2:
                    in_flight_started.set()
            assert release_in_flight.wait(2.0)
            return f"versionCode=1 minSdk=23 targetSdk=35\nversionName={args[3]}\n"
        raise AssertionError(f"Unexpected adb call: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)
    returned: list[dict[str, dict[str, str]]] = []
    worker = threading.Thread(
        target=lambda: returned.append(
            insights.collect_device_metadata_v9(
                "adb",
                packages,
                cancel_event=cancel_event,
                max_workers=2,
            )
        )
    )
    worker.start()
    assert in_flight_started.wait(2.0)
    cancel_event.set()
    release_in_flight.set()
    worker.join(2.0)

    assert not worker.is_alive()
    assert set(per_package) == {"pkg.0", "pkg.1"}
    assert set(returned[0]) == {"pkg.0", "pkg.1"}


def test_stop_during_adb_command_prevents_later_commands(monkeypatch) -> None:
    cancel_event = threading.Event()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(insights.state, "load_settings", lambda: {"permissions_audit_enabled": False})

    def fake_run(_adb: str, args: list[str], _timeout: int = 30) -> str:
        calls.append(tuple(args))
        if args == ["shell", "getprop"]:
            cancel_event.set()
            return "[ro.build.version.sdk]: [35]\n"
        raise AssertionError(f"Command started after Stop: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)

    assert insights.collect_device_metadata_v9(
        "adb", ["pkg.one"], cancel_event=cancel_event
    ) == {}
    assert calls == [("shell", "getprop")]


def test_stop_after_bulk_query_prevents_per_package_fallback(monkeypatch) -> None:
    cancel_event = threading.Event()
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(insights.state, "load_settings", lambda: {"permissions_audit_enabled": False})

    def fake_run(_adb: str, args: list[str], _timeout: int = 30) -> str:
        calls.append(tuple(args))
        if args == ["shell", "getprop"]:
            return "[ro.build.version.sdk]: [35]\n"
        if args in (
            ["shell", "pm", "list", "packages", "-d"],
            ["shell", "pm", "list", "packages", "-i"],
        ):
            return ""
        if args == ["shell", "dumpsys", "package"]:
            cancel_event.set()
            return ""
        raise AssertionError(f"Per-package command started after Stop: {args}")

    monkeypatch.setattr(insights, "_run", fake_run)

    assert insights.collect_device_metadata_v9(
        "adb", ["pkg.one", "pkg.two"], cancel_event=cancel_event
    ) == {}
    assert calls[-1] == ("shell", "dumpsys", "package")
    assert not [call for call in calls if len(call) == 4]

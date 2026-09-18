from __future__ import annotations

import pytest

from playstore_app_audit.services import connected_device_profile as connected_profile

COMPLETE_PROPERTIES = {
    "ro.hardware": "qcom",
    "gsm.version.baseband": "g5400c-240805-240927-B-12401357",
    "ro.bootloader": "caiman-15.0-12345678",
    "ro.build.fingerprint": "google/caiman/caiman:15/AP4A.250105.002/12345678:user/release-keys",
    "ro.product.brand": "google",
    "ro.product.device": "caiman",
    "ro.build.version.sdk": "35",
    "ro.build.version.release": "15",
    "ro.product.model": "Pixel 9 Pro",
    "ro.product.manufacturer": "Google",
    "ro.product.name": "caiman",
    "ro.build.id": "AP4A.250105.002",
    "ro.product.cpu.abilist": "arm64-v8a,armeabi-v7a",
    "ro.opengles.version": "196610",
    "persist.sys.timezone": "Europe/Zurich",
    "persist.sys.locales": "en-CH,it-IT",
}


def build_complete_profile() -> connected_profile.ConnectedDeviceProfile:
    return connected_profile.build_connected_device_profile(
        properties=COMPLETE_PROPERTIES,
        wm_size="Physical size: 1344x2992\nOverride size: 1080x2400\n",
        wm_density="Physical density: 490\nOverride density: 420\n",
        features=(
            "feature:android.hardware.camera\n"
            "feature:android.hardware.touchscreen\n"
            "reqGlEsVersion=0x30002\n"
        ),
        libraries="library:android.test.base\nlibrary:android.ext.shared\n",
        input_configuration=(
            "Configuration: touchScreen=3 keyboard=1 navigation=1 "
            "screenLayout=268435810\n"
        ),
        vending_package="versionCode=83911210 minSdk=23\nversionName=47.2.19-31\n",
        gsf_package="versionCode=253431037 minSdk=23\nversionName=15-12345678\n",
    )


def test_build_connected_device_profile_is_complete_and_stable() -> None:
    first = build_complete_profile()
    second = build_complete_profile()

    assert first.complete is True
    assert first.missing_fields == ()
    assert first.profile_id.startswith("connected_device_")
    assert first.profile_hash == second.profile_hash
    assert first.profile_id == second.profile_id
    assert first.display_name == "Google Pixel 9 Pro"
    assert first.android_release == "15"
    assert first.api_level == 35

    profile = dict(first.profile)
    assert profile["Screen.Width"] == "1080"
    assert profile["Screen.Height"] == "2400"
    assert profile["Screen.Density"] == "420"
    assert profile["TouchScreen"] == "3"
    assert profile["Keyboard"] == "1"
    assert profile["Navigation"] == "1"
    assert profile["ScreenLayout"] == "2"
    assert profile["HasHardKeyboard"] == "false"
    assert profile["HasFiveWayNavigation"] == "false"
    assert profile["Vending.version"] == "83911210"
    assert profile["Vending.versionString"] == "47.2.19-31"
    assert profile["GSF.version"] == "253431037"
    assert profile["Locales"] == "en_CH,it_IT"
    assert profile["Client"] == "android-google"


def test_sensitive_getprop_values_never_enter_connected_profile() -> None:
    properties = {
        **COMPLETE_PROPERTIES,
        "ro.serialno": "SECRET-SERIAL",
        "ro.boot.serialno": "SECRET-BOOT-SERIAL",
        "android_id": "SECRET-ANDROID-ID",
        "gsm.sim.operator.alpha": "Private Carrier",
        "gsm.sim.operator.numeric": "22801",
    }

    safe = connected_profile.safe_profile_properties(properties)
    profile = connected_profile.build_connected_device_profile(
        properties=properties,
        wm_size="Physical size: 1080x2400",
        wm_density="Physical density: 420",
        features="feature:android.hardware.touchscreen",
        libraries="library:android.test.base",
        input_configuration="touchScreen=3 keyboard=1 navigation=1 screenLayout=2",
        vending_package="versionCode=100\nversionName=1.0",
        gsf_package="versionCode=200\nversionName=2.0",
    )

    combined = repr(safe) + repr(dict(profile.profile))
    assert "SECRET" not in combined
    assert "serial" not in " ".join(profile.profile).casefold()
    assert "android_id" not in " ".join(profile.profile).casefold()
    assert "simoperator" not in "".join(profile.profile).casefold()
    assert "celloperator" not in "".join(profile.profile).casefold()


def test_incomplete_connected_profile_reports_missing_fields() -> None:
    result = connected_profile.build_connected_device_profile(
        properties={
            "ro.product.manufacturer": "Example",
            "ro.product.model": "Phone",
            "ro.build.version.sdk": "35",
            "ro.build.version.release": "15",
        },
        wm_size="",
        wm_density="",
        features="",
        libraries="",
        input_configuration="",
        vending_package="",
        gsf_package="",
    )

    assert result.complete is False
    assert "Build.FINGERPRINT" in result.missing_fields
    assert "Screen.Density" in result.missing_fields
    assert "Features" in result.missing_fields
    assert "GSF.version" in result.missing_fields
    assert "Vending.version" in result.missing_fields
    assert "Build.FINGERPRINT" not in result.profile
    assert "GSF.version" not in result.profile


def test_collect_connected_profile_uses_only_expected_read_only_adb_probes(
    monkeypatch,
) -> None:
    calls: list[tuple[str, ...]] = []
    serial = "ABC123"
    outputs = {
        ("devices",): f"List of devices attached\n{serial}\tdevice\n",
        ("-s", serial, "shell", "getprop"): "\n".join(
            f"[{key}]: [{value}]" for key, value in COMPLETE_PROPERTIES.items()
        ),
        ("-s", serial, "shell", "wm", "size"): "Physical size: 1080x2400",
        ("-s", serial, "shell", "wm", "density"): "Physical density: 420",
        ("-s", serial, "shell", "pm", "list", "features"): (
            "feature:android.hardware.touchscreen\nreqGlEsVersion=0x30002"
        ),
        ("-s", serial, "shell", "pm", "list", "libraries"): "library:android.test.base",
        ("-s", serial, "shell", "dumpsys", "input"): (
            "touchScreen=3 keyboard=1 navigation=1 screenLayout=2"
        ),
        ("-s", serial, "shell", "dumpsys", "package", "com.android.vending"): (
            "versionCode=100\nversionName=1.0"
        ),
        ("-s", serial, "shell", "dumpsys", "package", "com.google.android.gsf"): (
            "versionCode=200\nversionName=2.0"
        ),
    }

    def fake_run_adb(adb: str, *args: str, timeout: int):
        assert adb == "adb"
        assert timeout > 0
        calls.append(tuple(args))
        return type("Result", (), {"stdout": outputs.get(tuple(args), "")})()

    monkeypatch.setattr(connected_profile, "run_adb", fake_run_adb)

    result = connected_profile.collect_connected_device_profile("adb")

    assert result.complete is True
    assert calls == [
        ("devices",),
        ("-s", serial, "shell", "getprop"),
        ("-s", serial, "shell", "wm", "size"),
        ("-s", serial, "shell", "wm", "density"),
        ("-s", serial, "shell", "pm", "list", "features"),
        ("-s", serial, "shell", "pm", "list", "libraries"),
        ("-s", serial, "shell", "dumpsys", "input"),
        ("-s", serial, "shell", "dumpsys", "package", "com.android.vending"),
        ("-s", serial, "shell", "dumpsys", "package", "com.google.android.gsf"),
    ]
    returned = repr(dict(result.profile)).casefold()
    assert serial.casefold() not in returned
    assert "android_id" not in returned
    assert "gsf_id" not in returned
    joined = " ".join(" ".join(call) for call in calls).casefold()
    assert "iphonesubinfo" not in joined
    assert "account" not in joined


def test_collect_connected_profile_fails_loudly_without_authorised_device(
    monkeypatch,
) -> None:
    def fake_run_adb(adb: str, *args: str, timeout: int):
        assert adb == "adb"
        assert timeout > 0
        assert args == ("devices",)
        return type("Result", (), {"stdout": "List of devices attached\n"})()

    monkeypatch.setattr(connected_profile, "run_adb", fake_run_adb)

    with pytest.raises(RuntimeError, match="no authorised Android device"):
        connected_profile.collect_connected_device_profile("adb")

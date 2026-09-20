"""Privacy-safe Connected Device Play profile capture for Device Specific resolution.

The collector is deliberately on-demand. Normal Scan Phone stays on its compact ADB
path until the user explicitly selects Connected Device / Your Device for Device
Specific resolution.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from playstore_app_audit.devices.adb import run_adb
from playstore_app_audit.services import store_locale
from playstore_app_audit.services.device_specific_profiles import canonical_profile_hash

_SAFE_GETPROP_MAP = {
    "Build.HARDWARE": ("ro.hardware",),
    "Build.RADIO": ("gsm.version.baseband", "ro.boot.radio"),
    "Build.BOOTLOADER": ("ro.bootloader",),
    "Build.FINGERPRINT": ("ro.build.fingerprint",),
    "Build.BRAND": ("ro.product.brand",),
    "Build.DEVICE": ("ro.product.device",),
    "Build.VERSION.SDK_INT": ("ro.build.version.sdk",),
    "Build.VERSION.RELEASE": ("ro.build.version.release",),
    "Build.MODEL": ("ro.product.model",),
    "Build.MANUFACTURER": ("ro.product.manufacturer",),
    "Build.PRODUCT": ("ro.product.name", "ro.product.system.name"),
    "Build.ID": ("ro.build.id",),
    "Platforms": ("ro.product.cpu.abilist", "ro.product.cpu.abi"),
    "GL.Version": ("ro.opengles.version",),
    "TimeZone": ("persist.sys.timezone",),
}

# CellOperator / SimOperator / Roaming are intentionally not captured from the
# phone. Store country/network context belongs to the resolver request and is
# patched there. Identifiers/account material are forbidden entirely.
#
# Historical Aurora/goopdl profile compatibility keeps the field name
# "GSF.version", but the direct-auth protocol sends that value as
# google_play_services_version. Connected Device therefore sources it from
# com.google.android.gms, not com.google.android.gsf.
CONNECTED_REQUIRED_FIELDS = frozenset(
    {
        "UserReadableName",
        "Build.HARDWARE",
        "Build.RADIO",
        "Build.BOOTLOADER",
        "Build.FINGERPRINT",
        "Build.BRAND",
        "Build.DEVICE",
        "Build.VERSION.SDK_INT",
        "Build.VERSION.RELEASE",
        "Build.MODEL",
        "Build.MANUFACTURER",
        "Build.PRODUCT",
        "Build.ID",
        "TouchScreen",
        "Keyboard",
        "Navigation",
        "ScreenLayout",
        "HasHardKeyboard",
        "HasFiveWayNavigation",
        "GL.Version",
        "Screen.Density",
        "Screen.Width",
        "Screen.Height",
        "Platforms",
        "SharedLibraries",
        "Features",
        "Locales",
        "GSF.version",
        "Vending.version",
        "Vending.versionString",
        "TimeZone",
        "Client",
    }
)

_FORBIDDEN_KEY_PARTS = (
    "serial",
    "imei",
    "meid",
    "subscriber",
    "account",
    "email",
    "password",
    "cookie",
    "authtoken",
    "auth_token",
    "aastoken",
    "aas_token",
    "androidid",
    "android_id",
    "gsfid",
    "gsf_id",
)


@dataclass(frozen=True, slots=True)
class ConnectedDeviceProfile:
    profile_id: str
    display_name: str
    android_release: str
    api_level: int
    profile_hash: str
    profile: Mapping[str, str]
    complete: bool
    missing_fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ConnectedDeviceProfileCapture:
    """Complete profile plus an opaque, process-local device ownership token."""

    profile: ConnectedDeviceProfile
    ownership_token: str


def ephemeral_device_ownership_token(serial: str) -> str:
    """Derive the same non-reversible process-local ownership key as ScanSession."""

    return (
        hashlib.sha256(serial.encode("utf-8", errors="ignore")).hexdigest()[:16]
        if serial
        else "unknown"
    )


def _first(properties: Mapping[str, str], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(properties.get(key) or "").strip()
        if value:
            return value
    return ""


def safe_profile_properties(properties: Mapping[str, str]) -> dict[str, str]:
    """Return only allowlisted, non-identifier getprop evidence."""

    return {
        key: value
        for candidates in _SAFE_GETPROP_MAP.values()
        for key in candidates
        if (value := str(properties.get(key) or "").strip())
    } | {
        key: value
        for key in (
            "persist.sys.locales",
            "persist.sys.locale",
            "ro.product.locale",
        )
        if (value := str(properties.get(key) or "").strip())
    }


def _parse_wm_size(text: str) -> tuple[str, str]:
    matches = re.findall(r"(?:Physical|Override) size:\s*(\d+)x(\d+)", str(text or ""))
    if not matches:
        matches = re.findall(r"\b(\d+)x(\d+)\b", str(text or ""))
    if not matches:
        return "", ""
    width, height = matches[-1]
    return width, height


def _parse_wm_density(text: str) -> str:
    matches = re.findall(r"(?:Physical|Override) density:\s*(\d+)", str(text or ""))
    if not matches:
        matches = re.findall(r"\b(\d{2,4})\b", str(text or ""))
    return matches[-1] if matches else ""


def _parse_named_rows(text: str, prefix: str) -> str:
    values: set[str] = set()
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if value:
            values.add(value)
    return ",".join(sorted(values))


def _parse_resource_configuration(text: str) -> dict[str, str]:
    """Map Android resource qualifiers to Google Play profile input fields."""

    tokens = {
        token.casefold()
        for token in re.split(r"[\s-]+", str(text or "").strip())
        if token
    }
    result: dict[str, str] = {}

    if "finger" in tokens:
        result["TouchScreen"] = "3"
    elif "notouch" in tokens:
        result["TouchScreen"] = "1"

    keyboard_values = {"nokeys": "1", "qwerty": "2", "12key": "3"}
    for token, value in keyboard_values.items():
        if token in tokens:
            result["Keyboard"] = value
            break

    navigation_values = {
        "nonav": "1",
        "dpad": "2",
        "trackball": "3",
        "wheel": "4",
    }
    for token, value in navigation_values.items():
        if token in tokens:
            result["Navigation"] = value
            break

    screen_layout_values = {
        "small": "1",
        "smll": "1",
        "normal": "2",
        "nrml": "2",
        "large": "3",
        "lrg": "3",
        "xlarge": "4",
        "xlrg": "4",
    }
    for token, value in screen_layout_values.items():
        if token in tokens:
            result["ScreenLayout"] = value
            break

    return result


def _parse_input_configuration(
    text: str,
    resource_configuration: str = "",
) -> dict[str, str]:
    source = str(text or "")
    patterns = {
        "TouchScreen": r"(?i)\btouch(?:screen|Screen)\s*[=:]\s*(\d+)",
        "Keyboard": r"(?i)\bkeyboard\s*[=:]\s*(\d+)",
        "Navigation": r"(?i)\bnavigation\s*[=:]\s*(\d+)",
        "ScreenLayout": r"(?i)\bscreenLayout\s*[=:]\s*(\d+)",
    }
    result: dict[str, str] = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, source)
        if match:
            value = int(match.group(1))
            if key == "ScreenLayout":
                value &= 0x0F
            if value > 0:
                result[key] = str(value)

    fallback = _parse_resource_configuration(resource_configuration)
    for key, value in fallback.items():
        result.setdefault(key, value)

    keyboard = result.get("Keyboard")
    if keyboard:
        result["HasHardKeyboard"] = "false" if keyboard == "1" else "true"
    navigation = result.get("Navigation")
    if navigation:
        result["HasFiveWayNavigation"] = (
            "true" if navigation in {"2", "3"} else "false"
        )
    return result


def _parse_package_version(
    text: str,
    version_code_listing: str = "",
) -> tuple[str, str]:
    source = str(text or "")
    listing = str(version_code_listing or "")
    listed_code = re.search(r"\bversionCode[:=](\d+)\b", listing)
    dumped_code = re.search(r"\bversionCode=(\d+)\b", source)
    name = re.search(r"\bversionName=([^\r\n]+)", source)
    code = listed_code or dumped_code
    return (
        code.group(1) if code else "",
        name.group(1).strip() if name else "",
    )


def _normalise_locales(properties: Mapping[str, str]) -> str:
    raw = _first(
        properties,
        ("persist.sys.locales", "persist.sys.locale", "ro.product.locale"),
    )
    if not raw:
        return ""
    values = [part.strip().replace("-", "_") for part in raw.split(",") if part.strip()]
    return ",".join(dict.fromkeys(values))


def _validate_profile_keys(profile: Mapping[str, str]) -> None:
    for key in profile:
        compact = key.casefold().replace(".", "").replace("-", "")
        if any(marker in compact for marker in _FORBIDDEN_KEY_PARTS):
            raise ValueError(f"connected profile contains forbidden key: {key}")


def build_connected_device_profile(
    *,
    properties: Mapping[str, str],
    wm_size: str,
    wm_density: str,
    features: str,
    libraries: str,
    input_configuration: str,
    vending_package: str,
    play_services_package: str,
    resource_configuration: str = "",
    vending_version_code_listing: str = "",
    play_services_version_code_listing: str = "",
) -> ConnectedDeviceProfile:
    safe_properties = safe_profile_properties(properties)
    profile: dict[str, str] = {}

    for target, candidates in _SAFE_GETPROP_MAP.items():
        value = _first(safe_properties, candidates)
        if value:
            profile[target] = value

    width, height = _parse_wm_size(wm_size)
    density = _parse_wm_density(wm_density)
    if width:
        profile["Screen.Width"] = width
    if height:
        profile["Screen.Height"] = height
    if density:
        profile["Screen.Density"] = density

    feature_list = _parse_named_rows(features, "feature:")
    library_list = _parse_named_rows(libraries, "library:")
    if feature_list:
        profile["Features"] = feature_list
    if library_list:
        profile["SharedLibraries"] = library_list

    if "GL.Version" not in profile:
        gl_match = re.search(r"reqGlEsVersion\s*[=:]\s*(0x[0-9a-fA-F]+|\d+)", features)
        if gl_match:
            raw_gl = gl_match.group(1)
            profile["GL.Version"] = str(int(raw_gl, 16 if raw_gl.startswith("0x") else 10))

    profile.update(
        _parse_input_configuration(input_configuration, resource_configuration)
    )

    vending_code, vending_name = _parse_package_version(
        vending_package, vending_version_code_listing
    )
    play_services_code, _play_services_name = _parse_package_version(
        play_services_package,
        play_services_version_code_listing,
    )
    if vending_code:
        profile["Vending.version"] = vending_code
    if vending_name:
        profile["Vending.versionString"] = vending_name
    if play_services_code:
        # Legacy profile key; semantically this is Google Play services.
        profile["GSF.version"] = play_services_code

    locales = _normalise_locales(safe_properties)
    if locales:
        profile["Locales"] = locales

    manufacturer = profile.get("Build.MANUFACTURER", "").strip()
    model = profile.get("Build.MODEL", "").strip()
    android_release = profile.get("Build.VERSION.RELEASE", "").strip()
    readable = " ".join(part for part in (manufacturer, model) if part).strip()
    if readable:
        profile["UserReadableName"] = readable

    # Protocol invariant, not account or device identity.
    profile["Client"] = "android-google"

    _validate_profile_keys(profile)
    missing = tuple(sorted(CONNECTED_REQUIRED_FIELDS - set(profile)))
    profile_hash = canonical_profile_hash(profile)
    profile_id = f"connected_device_{profile_hash[:12]}"
    try:
        api_level = int(profile.get("Build.VERSION.SDK_INT") or 0)
    except ValueError:
        api_level = 0

    return ConnectedDeviceProfile(
        profile_id=profile_id,
        display_name=readable or "Connected Device",
        android_release=android_release,
        api_level=api_level,
        profile_hash=profile_hash,
        profile=MappingProxyType(dict(profile)),
        complete=not missing and api_level > 0,
        missing_fields=missing,
    )


def _authorised_device_serial(adb: str) -> str:
    """Return the one authorised ADB serial for command targeting only."""

    try:
        output = str(run_adb(adb, "devices", timeout=20).stdout or "")
    except Exception:
        raise RuntimeError("ADB could not enumerate connected Android devices.") from None

    authorised: list[str] = []
    unauthorised = False
    offline = False
    for raw_line in output.splitlines()[1:]:
        parts = raw_line.split()
        if len(parts) < 2:
            continue
        state = parts[1]
        if state == "device":
            authorised.append(parts[0])
        elif state == "unauthorized":
            unauthorised = True
        elif state == "offline":
            offline = True

    if len(authorised) == 1:
        return authorised[0]
    if len(authorised) > 1:
        raise RuntimeError(
            "More than one authorised Android device is visible to ADB. "
            "Keep only the phone you want to use connected."
        )
    if unauthorised:
        raise RuntimeError(
            "The Android device is visible to ADB but is not authorised. "
            "Unlock it and accept the USB debugging prompt."
        )
    if offline:
        raise RuntimeError(
            "The Android device is visible to ADB but is offline. Reconnect it and try again."
        )
    raise RuntimeError("ADB can see no authorised Android device.")


def _required_device_stdout(
    adb: str,
    serial: str,
    *args: str,
    timeout: int,
    label: str,
) -> str:
    try:
        return str(run_adb(adb, "-s", serial, *args, timeout=timeout).stdout or "")
    except Exception:
        raise RuntimeError(f"ADB could not read the connected device {label}.") from None


def _optional_device_stdout(adb: str, serial: str, *args: str, timeout: int) -> str:
    try:
        return str(run_adb(adb, "-s", serial, *args, timeout=timeout).stdout or "")
    except Exception:
        return ""


def collect_connected_device_profile(
    adb: str,
    *,
    properties: Mapping[str, str] | None = None,
    serial: str | None = None,
) -> ConnectedDeviceProfile:
    """Collect one on-demand, read-only Play-targeting profile over ADB.

    The function never reads account identifiers, Android ID, GSF ID, IMEI/MEID or
    subscriber/SIM identifiers. The raw ADB serial is used only transiently as the
    command-local adb -s selector and is never returned, persisted or logged.
    Network/operator context is deliberately left to the resolver request.
    """

    serial = serial or _authorised_device_serial(adb)

    if properties is None:
        getprop = _required_device_stdout(
            adb,
            serial,
            "shell",
            "getprop",
            timeout=25,
            label="properties",
        )
        properties = store_locale.parse_getprop_output(getprop)
        if not properties:
            raise RuntimeError("ADB returned no readable Android device properties.")

    return build_connected_device_profile(
        properties=properties,
        wm_size=_optional_device_stdout(
            adb, serial, "shell", "wm", "size", timeout=15
        ),
        wm_density=_optional_device_stdout(
            adb, serial, "shell", "wm", "density", timeout=15
        ),
        features=_optional_device_stdout(
            adb, serial, "shell", "pm", "list", "features", timeout=30
        ),
        libraries=_optional_device_stdout(
            adb, serial, "shell", "pm", "list", "libraries", timeout=30
        ),
        input_configuration=_optional_device_stdout(
            adb, serial, "shell", "dumpsys", "input", timeout=30
        ),
        resource_configuration=_optional_device_stdout(
            adb, serial, "shell", "cmd", "activity", "get-config", timeout=20
        ),
        vending_package=_optional_device_stdout(
            adb,
            serial,
            "shell",
            "dumpsys",
            "package",
            "com.android.vending",
            timeout=30,
        ),
        vending_version_code_listing=_optional_device_stdout(
            adb,
            serial,
            "shell",
            "pm",
            "list",
            "packages",
            "--show-versioncode",
            "com.android.vending",
            timeout=20,
        ),
        play_services_package=_optional_device_stdout(
            adb,
            serial,
            "shell",
            "dumpsys",
            "package",
            "com.google.android.gms",
            timeout=30,
        ),
        play_services_version_code_listing=_optional_device_stdout(
            adb,
            serial,
            "shell",
            "pm",
            "list",
            "packages",
            "--show-versioncode",
            "com.google.android.gms",
            timeout=20,
        ),
    )


def capture_connected_device_profile(adb: str) -> ConnectedDeviceProfileCapture:
    """Capture a profile and safe ownership token with one ADB enumeration.

    The raw serial remains command-local: it selects the device for the allowlisted
    profile reads and is never returned, logged or persisted.
    """

    serial = _authorised_device_serial(adb)
    return ConnectedDeviceProfileCapture(
        profile=collect_connected_device_profile(adb, serial=serial),
        ownership_token=ephemeral_device_ownership_token(serial),
    )

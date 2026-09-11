from __future__ import annotations

import logging
import subprocess
import sys
from ctypes import POINTER, byref, c_int, c_long, c_void_p, wintypes
from pathlib import Path
from typing import Any

from playstore_app_audit.platform import runtime

logger = logging.getLogger(__name__)

_COINIT_APARTMENTTHREADED = 0x2
_RPC_E_CHANGED_MODE = 0x80010106


def _hresult_succeeded(value: int) -> bool:
    return c_int(value).value >= 0


def _windows_initialize_com(ole32: Any) -> tuple[bool, bool, int]:
    """Ensure COM is available on the calling thread for Shell selection APIs.

    Returns ``(ready, must_uninitialize, hresult)``. ``RPC_E_CHANGED_MODE`` means
    the thread already has COM initialized with a different apartment model, so
    Shell APIs may still be used but this helper must not uninitialize that
    caller-owned COM state.
    """

    ole32.CoInitializeEx.argtypes = [c_void_p, wintypes.DWORD]
    ole32.CoInitializeEx.restype = c_long
    ole32.CoUninitialize.argtypes = []
    ole32.CoUninitialize.restype = None
    result = int(ole32.CoInitializeEx(None, _COINIT_APARTMENTTHREADED))
    if _hresult_succeeded(result):
        return True, True, result
    if result & 0xFFFFFFFF == _RPC_E_CHANGED_MODE:
        return True, False, result
    return False, False, result


def _windows_reveal_file(path: Path) -> tuple[bool, int]:
    """Select *path* with the Shell API and release every allocated PIDL."""

    if sys.platform != "win32":
        return False, -1

    import ctypes

    shell32 = ctypes.windll.shell32
    ole32 = ctypes.windll.ole32
    shell32.SHParseDisplayName.argtypes = [
        wintypes.LPCWSTR,
        c_void_p,
        POINTER(c_void_p),
        wintypes.DWORD,
        POINTER(wintypes.DWORD),
    ]
    shell32.SHParseDisplayName.restype = c_long
    shell32.ILFindLastID.argtypes = [c_void_p]
    shell32.ILFindLastID.restype = c_void_p
    shell32.SHOpenFolderAndSelectItems.argtypes = [
        c_void_p,
        wintypes.UINT,
        POINTER(c_void_p),
        wintypes.DWORD,
    ]
    shell32.SHOpenFolderAndSelectItems.restype = c_long
    ole32.CoTaskMemFree.argtypes = [c_void_p]
    ole32.CoTaskMemFree.restype = None

    com_ready, must_uninitialize, com_result = _windows_initialize_com(ole32)
    if not com_ready:
        return False, com_result

    try:
        folder_pidl = c_void_p()
        item_pidl = c_void_p()
        attributes = wintypes.DWORD()
        result = int(
            shell32.SHParseDisplayName(
                str(path.parent), None, byref(folder_pidl), 0, byref(attributes)
            )
        )
        if not _hresult_succeeded(result):
            if folder_pidl.value:
                ole32.CoTaskMemFree(folder_pidl)
            return False, result
        try:
            result = int(
                shell32.SHParseDisplayName(
                    str(path), None, byref(item_pidl), 0, byref(attributes)
                )
            )
            if not _hresult_succeeded(result):
                if item_pidl.value:
                    ole32.CoTaskMemFree(item_pidl)
                return False, result
            try:
                child_pidl = shell32.ILFindLastID(item_pidl)
                if not child_pidl:
                    return False, -1
                children = (c_void_p * 1)(child_pidl)
                result = int(shell32.SHOpenFolderAndSelectItems(folder_pidl, 1, children, 0))
                return _hresult_succeeded(result), result
            finally:
                ole32.CoTaskMemFree(item_pidl)
        finally:
            ole32.CoTaskMemFree(folder_pidl)
    finally:
        if must_uninitialize:
            ole32.CoUninitialize()


def _windows_open_folder(path: Path) -> tuple[bool, int]:
    """Open an existing folder and report the ShellExecute result."""

    if sys.platform != "win32":
        return False, 0

    import ctypes

    shell32 = ctypes.windll.shell32
    shell32.ShellExecuteW.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        c_int,
    ]
    shell32.ShellExecuteW.restype = wintypes.HINSTANCE
    result = int(shell32.ShellExecuteW(None, "open", str(path), None, None, 1))
    return result > 32, result


def open_file_location(value: object) -> tuple[bool, str]:
    """Reveal one existing local file using argument-safe platform commands."""

    platform = runtime.platform_key()
    path = Path(str(value or "")).expanduser()
    logger.debug("Local APK reveal requested: platform=%s path=%s", platform, path)
    if not path.is_file():
        logger.warning(
            "Local APK reveal failed: platform=%s reason=missing path=%s", platform, path
        )
        logger.info(
            "Local APK reveal final outcome: platform=%s success=false path=%s", platform, path
        )
        return False, "The local APK file is no longer available at this location."
    path = path.resolve(strict=True)
    try:
        if platform == "windows":
            opened, result = _windows_reveal_file(path)
            if opened:
                logger.info(
                    "Local APK native reveal succeeded: platform=windows hresult=%#x path=%s",
                    result & 0xFFFFFFFF,
                    path,
                )
            else:
                logger.warning(
                    "Local APK native reveal failed: platform=windows hresult=%#x path=%s",
                    result & 0xFFFFFFFF,
                    path,
                )
                fallback_opened, fallback_result = _windows_open_folder(path.parent)
                logger.info(
                    "Local APK parent-folder fallback: platform=windows result=%d "
                    "success=%s path=%s",
                    fallback_result,
                    fallback_opened,
                    path.parent,
                )
                if not fallback_opened:
                    logger.warning(
                        "Local APK reveal final outcome: platform=windows success=false path=%s",
                        path,
                    )
                    return False, "The file could not be selected and its folder could not be opened."
        elif platform == "macos":
            subprocess.Popen(["open", "-R", str(path)], close_fds=True)
        else:
            subprocess.Popen(["xdg-open", str(path.parent)], close_fds=True)
    except OSError as exc:
        logger.exception("Local APK reveal failed: platform=%s path=%s", platform, path)
        logger.warning(
            "Local APK reveal final outcome: platform=%s success=false path=%s", platform, path
        )
        return False, f"The file location could not be opened: {exc}"
    logger.info("Local APK reveal final outcome: platform=%s success=true path=%s", platform, path)
    return True, ""

from __future__ import annotations

import ctypes
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

import pytest

import playstore_app_audit.platform.file_locations as file_locations


class _FakeFunction:
    def __init__(self, callback: Callable[..., Any]) -> None:
        self._callback = callback
        self.calls: list[tuple[object, ...]] = []
        self.argtypes: object = None
        self.restype: object = None

    def __call__(self, *args: object) -> Any:
        self.calls.append(args)
        return self._callback(*args)


def _ole32(init_result: int) -> SimpleNamespace:
    return SimpleNamespace(
        CoInitializeEx=_FakeFunction(lambda *_args: init_result),
        CoUninitialize=_FakeFunction(lambda: None),
        CoTaskMemFree=_FakeFunction(lambda _value: None),
    )


def test_windows_com_initialization_balances_owned_apartment() -> None:
    ole32 = _ole32(0)

    ready, must_uninitialize, result = file_locations._windows_initialize_com(ole32)

    assert (ready, must_uninitialize, result) == (True, True, 0)
    assert len(ole32.CoInitializeEx.calls) == 1


def test_windows_com_changed_mode_reuses_caller_owned_apartment() -> None:
    ole32 = _ole32(-2147417850)  # RPC_E_CHANGED_MODE / 0x80010106

    ready, must_uninitialize, result = file_locations._windows_initialize_com(ole32)

    assert ready
    assert not must_uninitialize
    assert result & 0xFFFFFFFF == file_locations._RPC_E_CHANGED_MODE


def test_windows_com_hard_failure_blocks_shell_selection() -> None:
    ole32 = _ole32(-2147467259)  # E_FAIL

    ready, must_uninitialize, result = file_locations._windows_initialize_com(ole32)

    assert not ready
    assert not must_uninitialize
    assert result < 0


def test_windows_native_reveal_initializes_and_uninitializes_com(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    allocated = iter((0x1000, 0x2000))

    def parse_display_name(
        _name: object,
        _bind_context: object,
        out_pidl: object,
        _attributes_mask: object,
        _attributes: object,
    ) -> int:
        out_pidl._obj.value = next(allocated)  # type: ignore[attr-defined]
        return 0

    shell32 = SimpleNamespace(
        SHParseDisplayName=_FakeFunction(parse_display_name),
        ILFindLastID=_FakeFunction(lambda _pidl: 0x3000),
        SHOpenFolderAndSelectItems=_FakeFunction(lambda *_args: 0),
    )
    ole32 = _ole32(0)
    monkeypatch.setattr(file_locations.sys, "platform", "win32")
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(shell32=shell32, ole32=ole32),
        raising=False,
    )

    opened, result = file_locations._windows_reveal_file(
        Path(r"C:\folder with spaces\caffè_日本 #1.apk")
    )

    assert opened
    assert result == 0
    assert len(ole32.CoInitializeEx.calls) == 1
    assert len(ole32.CoUninitialize.calls) == 1
    assert len(ole32.CoTaskMemFree.calls) == 2
    assert len(shell32.SHOpenFolderAndSelectItems.calls) == 1

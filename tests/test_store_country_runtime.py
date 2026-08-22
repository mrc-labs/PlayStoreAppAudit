from __future__ import annotations

import pytest

from playstore_app_audit.platform import runtime


def _clear_locale_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)


def test_host_store_country_reads_desktop_locale_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    _clear_locale_environment(monkeypatch)
    monkeypatch.setenv("LANG", "it_CH.UTF-8")

    assert runtime.detect_host_store_country() == "ch"
    assert runtime.detect_store_country() == "ch"


def test_store_country_uses_us_only_after_host_detection_is_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(runtime.platform, "system", lambda: "Linux")
    _clear_locale_environment(monkeypatch)
    monkeypatch.setattr(runtime.locale, "getlocale", lambda: (None, None))

    assert runtime.detect_host_store_country() is None
    assert runtime.detect_store_country() == "us"

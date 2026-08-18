from __future__ import annotations

from collections.abc import Callable

import prepare_release_legal_bundle as legal
import pytest

DIGEST = "0123456789abcdef" * 4
BASE_URL = "https://download.qt.io/example/source.tar.xz"


def _downloader(
    mapping: dict[str, str],
) -> Callable[[str], str]:
    def download(url: str) -> str:
        try:
            return mapping[url]
        except KeyError as exc:
            raise RuntimeError(f"unavailable: {url}") from exc

    return download


def test_qt_sha256_reads_meta4_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta4 = (
        '<metalink xmlns="urn:ietf:params:xml:ns:metalink">'
        f'<file name="source.tar.xz"><hash type="sha-256">'
        f"{DIGEST}</hash></file></metalink>"
    )
    monkeypatch.setattr(
        legal,
        "_download_text",
        _downloader({f"{BASE_URL}.meta4": meta4}),
    )

    assert legal._qt_official_sha256(BASE_URL) == (
        DIGEST,
        f"{BASE_URL}.meta4",
    )


def test_qt_sha256_accepts_hash_value_attribute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meta4 = (
        "<metalink><file>"
        f'<hash type="SHA_256" value="{DIGEST.upper()}" />'
        "</file></metalink>"
    )
    monkeypatch.setattr(
        legal,
        "_download_text",
        _downloader({f"{BASE_URL}.meta4": meta4}),
    )

    assert legal._qt_official_sha256(BASE_URL) == (
        DIGEST,
        f"{BASE_URL}.meta4",
    )


def test_qt_sha256_falls_back_to_legacy_metalink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = (
        "<metalink><files><file><verification>"
        f'<hash type="sha256">{DIGEST}</hash>'
        "</verification></file></files></metalink>"
    )
    monkeypatch.setattr(
        legal,
        "_download_text",
        _downloader(
            {
                f"{BASE_URL}.meta4": "<metalink />",
                f"{BASE_URL}.metalink": legacy,
            }
        ),
    )

    assert legal._qt_official_sha256(BASE_URL) == (
        DIGEST,
        f"{BASE_URL}.metalink",
    )


def test_qt_sha256_falls_back_to_mirrorlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mirrorlist = (
        "<html><body>SHA 256 Hash: "
        f"<code>{DIGEST.upper()}</code></body></html>"
    )
    monkeypatch.setattr(
        legal,
        "_download_text",
        _downloader(
            {
                f"{BASE_URL}.meta4": "<metalink />",
                f"{BASE_URL}.metalink": "<metalink />",
                f"{BASE_URL}.mirrorlist": mirrorlist,
            }
        ),
    )

    assert legal._qt_official_sha256(BASE_URL) == (
        DIGEST,
        f"{BASE_URL}.mirrorlist",
    )


def test_qt_sha256_resolver_remains_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        legal,
        "_download_text",
        _downloader(
            {
                f"{BASE_URL}.meta4": "<metalink />",
                f"{BASE_URL}.metalink": "<metalink />",
                f"{BASE_URL}.mirrorlist": "<html>No hash yet</html>",
            }
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Unable to obtain official Qt SHA-256 metadata",
    ):
        legal._qt_official_sha256(BASE_URL)

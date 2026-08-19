from __future__ import annotations

import hashlib
import io
from pathlib import Path

import prepare_release_legal_bundle as legal
import pytest


class _ChunkedResponse:
    def __init__(self, payload: bytes, *, fail_on_second_read: bool = False) -> None:
        self.payload = payload
        self.fail_on_second_read = fail_on_second_read
        self.read_count = 0
        self.offset = 0

    def __enter__(self) -> _ChunkedResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self, _size: int = -1) -> bytes:
        self.read_count += 1

        if self.fail_on_second_read and self.read_count == 2:
            raise TimeoutError("simulated mid-stream timeout")

        if self.offset >= len(self.payload):
            return b""

        split = max(1, len(self.payload) // 2)
        end = min(len(self.payload), self.offset + split)
        chunk = self.payload[self.offset:end]
        self.offset = end
        return chunk


def test_download_file_retries_mid_stream_timeout_without_partial_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"verified immutable source archive payload"
    expected_sha256 = hashlib.sha256(payload).hexdigest()
    destination = tmp_path / "source.tar.xz"
    attempts = 0

    def open_url(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 2:
            assert list(tmp_path.glob("*.download")) == []
        return _ChunkedResponse(
            payload,
            fail_on_second_read=attempts == 1,
        )

    monkeypatch.setattr(legal, "_open_url_with_retry", open_url)
    monkeypatch.setattr(legal.time, "sleep", lambda _delay: None)

    legal._download_file(
        "https://example.invalid/source.tar.xz",
        destination,
        expected_sha256,
    )

    assert attempts == 2
    assert destination.read_bytes() == payload
    assert hashlib.sha256(destination.read_bytes()).hexdigest() == expected_sha256
    assert list(tmp_path.glob("*.download")) == []


def test_download_file_does_not_retry_sha256_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "source.tar.xz"
    attempts = 0

    def open_url(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        return io.BytesIO(b"wrong payload")

    monkeypatch.setattr(legal, "_open_url_with_retry", open_url)

    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        legal._download_file(
            "https://example.invalid/source.tar.xz",
            destination,
            hashlib.sha256(b"expected payload").hexdigest(),
        )

    assert attempts == 1
    assert not destination.exists()
    assert list(tmp_path.glob("*.download")) == []


def test_download_file_reuses_existing_verified_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"already verified source archive"
    destination = tmp_path / "source.tar.xz"
    destination.write_bytes(payload)

    def unexpected_open(*_args, **_kwargs):
        raise AssertionError("network must not be used for a verified existing file")

    monkeypatch.setattr(legal, "_open_url_with_retry", unexpected_open)

    legal._download_file(
        "https://example.invalid/source.tar.xz",
        destination,
        hashlib.sha256(payload).hexdigest(),
    )

    assert destination.read_bytes() == payload


def test_download_text_retries_read_timeout_and_caches_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.invalid/source.meta4"
    payload = b"<metalink>verified metadata</metalink>"
    attempts = 0

    class _TimeoutResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def read(self) -> bytes:
            raise TimeoutError("simulated metadata read timeout")

    def open_url(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return _TimeoutResponse()
        return io.BytesIO(payload)

    legal._TEXT_DOWNLOAD_CACHE.clear()
    monkeypatch.setattr(legal, "_open_url_with_retry", open_url)
    monkeypatch.setattr(legal.time, "sleep", lambda _delay: None)

    expected = payload.decode("utf-8")
    assert legal._download_text(url) == expected
    assert legal._download_text(url) == expected
    assert attempts == 2

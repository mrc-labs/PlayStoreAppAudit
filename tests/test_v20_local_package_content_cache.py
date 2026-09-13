from __future__ import annotations

import hashlib
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import pytest

from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFormat,
    LocalArtifactParseResult,
)
from playstore_app_audit.services import local_package_metadata_cache


def _artifact(path: Path) -> LocalArtifact:
    canonical = path.resolve()
    stat = canonical.stat()
    digest = hashlib.sha256(canonical.read_bytes()).hexdigest()
    return LocalArtifact(
        artifact_format=LocalArtifactFormat.APK,
        artifact_sha256=digest,
        package_id="com.example.cached",
        application_label="Cached",
        application_label_reference=None,
        version_name="1.0",
        version_name_reference=None,
        version_code=1,
        version_code_major=None,
        min_sdk=23,
        target_sdk=35,
        compile_sdk=35,
        application_debuggable=False,
        permissions=(),
        features=(),
        icon_reference=None,
        file_name=canonical.name,
        canonical_path=canonical,
        file_size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
    )


def _install_fake_parser(
    monkeypatch: pytest.MonkeyPatch,
    *,
    before_return: threading.Event | None = None,
    release: threading.Event | None = None,
) -> list[Path]:
    calls: list[Path] = []

    def parse(path: str | Path, *, cancel_event=None) -> LocalArtifactParseResult:
        del cancel_event
        resolved = Path(path).resolve()
        calls.append(resolved)
        if before_return is not None:
            before_return.set()
        if release is not None:
            assert release.wait(timeout=5)
        return LocalArtifactParseResult(artifact=_artifact(resolved))

    monkeypatch.setattr(local_package_metadata_cache, "parse_local_package", parse)
    return calls


def test_tier2_reuses_identical_content_after_rename_without_reparse(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(local_package_metadata_cache, "app_data_dir", lambda: cache_root)
    calls = _install_fake_parser(monkeypatch)
    first = tmp_path / "first.apk"
    second = tmp_path / "renamed.apk"
    payload = b"same exact APK bytes"
    first.write_bytes(payload)
    second.write_bytes(payload)

    first_result, first_hit = local_package_metadata_cache.parse_cached_local_package(first)
    assert first_result.artifact is not None
    assert first_hit is False
    assert calls == [first.resolve()]

    caplog.set_level(logging.DEBUG, logger=local_package_metadata_cache.__name__)
    second_result, second_hit = local_package_metadata_cache.parse_cached_local_package(second)

    assert second_hit is True
    assert second_result.artifact is not None
    assert second_result.artifact.artifact_sha256 == hashlib.sha256(payload).hexdigest()
    assert second_result.artifact.canonical_path == second.resolve()
    assert second_result.artifact.file_name == second.name
    assert second_result.artifact.file_size == second.stat().st_size
    assert calls == [first.resolve()]
    assert local_package_metadata_cache.entry_count() == 2
    assert any("cache=tier2" in record.getMessage() for record in caplog.records)


def test_cold_unique_file_does_not_gain_pre_hash_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(local_package_metadata_cache, "app_data_dir", lambda: cache_root)
    calls = _install_fake_parser(monkeypatch)
    apk = tmp_path / "unique.apk"
    apk.write_bytes(b"unique size/content")

    def unexpected_probe(*_args, **_kwargs):
        raise AssertionError("cold unique file should not be pre-hashed by tier 2")

    monkeypatch.setattr(local_package_metadata_cache, "_stable_sha256", unexpected_probe)

    result, hit = local_package_metadata_cache.parse_cached_local_package(apk)

    assert result.artifact is not None
    assert hit is False
    assert calls == [apk.resolve()]


def test_same_size_different_content_probes_then_parses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(local_package_metadata_cache, "app_data_dir", lambda: cache_root)
    calls = _install_fake_parser(monkeypatch)
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"AAAA")
    second.write_bytes(b"BBBB")

    _, first_hit = local_package_metadata_cache.parse_cached_local_package(first)
    second_result, second_hit = local_package_metadata_cache.parse_cached_local_package(second)

    assert first_hit is False
    assert second_hit is False
    assert second_result.artifact is not None
    assert calls == [first.resolve(), second.resolve()]


def test_same_batch_identical_bytes_are_content_deduplicated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache_root = tmp_path / "cache"
    cache_root.mkdir()
    monkeypatch.setattr(local_package_metadata_cache, "app_data_dir", lambda: cache_root)
    first_started = threading.Event()
    release_first = threading.Event()
    calls = _install_fake_parser(
        monkeypatch,
        before_return=first_started,
        release=release_first,
    )
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    payload = b"identical concurrent APK bytes"
    first.write_bytes(payload)
    second.write_bytes(payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(local_package_metadata_cache.parse_cached_local_package, first)
        assert first_started.wait(timeout=5)
        second_future = pool.submit(local_package_metadata_cache.parse_cached_local_package, second)
        release_first.set()
        first_result, first_hit = first_future.result(timeout=5)
        second_result, second_hit = second_future.result(timeout=5)

    assert first_result.artifact is not None
    assert second_result.artifact is not None
    assert sorted((first_hit, second_hit)) == [False, True]
    assert len(calls) == 1
    assert local_package_metadata_cache.entry_count() == 2

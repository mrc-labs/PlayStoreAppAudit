from __future__ import annotations

import hashlib
import json
import os
import stat
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest

import playstore_app_audit.services.local_apk_library as library_service_module
from playstore_app_audit.domain.local_apk_library import (
    LOCAL_APK_LIBRARY_SCHEMA_VERSION,
    LibraryLoadFailureKind,
    LibraryRootScanStatus,
    LibraryScanIssueKind,
    LocalApkLibrary,
)
from playstore_app_audit.domain.local_artifacts import (
    LocalArtifact,
    LocalArtifactFailureKind,
    LocalArtifactFormat,
    LocalArtifactParseFailure,
    LocalArtifactParseResult,
    LocalArtifactWarning,
)
from playstore_app_audit.services.local_apk_library import (
    LIBRARY_FILENAME,
    LocalApkLibraryService,
)

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=UTC)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fake_parser(path: Path) -> LocalArtifactParseResult:
    if path.name.casefold().startswith("bad"):
        return LocalArtifactParseResult(
            failure=LocalArtifactParseFailure(
                path,
                LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                "Malformed test APK.",
            )
        )
    if path.name.casefold().startswith("unreadable"):
        return LocalArtifactParseResult(
            failure=LocalArtifactParseFailure(
                path,
                LocalArtifactFailureKind.IO_ERROR,
                "Unreadable test APK.",
            )
        )
    data = path.read_bytes()
    package = "com.example.shared" if data.startswith(b"shared") else f"com.example.{data.hex()}"
    file_stat = path.stat()
    return LocalArtifactParseResult(
        artifact=LocalArtifact(
            artifact_format=LocalArtifactFormat.APK,
            artifact_sha256=_sha(data),
            package_id=package,
            application_label=f"Label {path.stem}",
            application_label_reference="@string/app_name",
            version_name="1.0",
            version_name_reference=None,
            version_code=10,
            version_code_major=None,
            min_sdk=23,
            target_sdk=35,
            compile_sdk=35,
            application_debuggable=False,
            permissions=("android.permission.INTERNET",),
            features=("android.hardware.camera",),
            icon_reference="@mipmap/ic_launcher",
            file_name=path.name,
            canonical_path=path.resolve(),
            file_size=file_stat.st_size,
            modified_at=datetime.fromtimestamp(file_stat.st_mtime, tz=UTC),
            warnings=(LocalArtifactWarning.APPLICATION_LABEL_UNRESOLVED,),
        )
    )


def _service(tmp_path: Path, **kwargs: object) -> LocalApkLibraryService:
    return LocalApkLibraryService(
        tmp_path / LIBRARY_FILENAME,
        parser=kwargs.get("parser", _fake_parser),  # type: ignore[arg-type]
        clock=lambda: NOW,
    )


def _scan(service: LocalApkLibraryService, root: Path) -> LocalApkLibrary:
    library = service.register_roots(service.empty_library(), [root])
    return service.rescan(library).library


def test_empty_library_creation_and_load(tmp_path: Path) -> None:
    service = _service(tmp_path)

    result = service.load()

    assert result.succeeded
    assert result.library == LocalApkLibrary()
    assert not service.path.exists()


def test_schema_v1_round_trip_and_deterministic_persistence(tmp_path: Path) -> None:
    first_root = tmp_path / "z-root"
    second_root = tmp_path / "a-root"
    first_root.mkdir()
    second_root.mkdir()
    (first_root / "z.apk").write_bytes(b"z")
    (second_root / "a.apk").write_bytes(b"a")
    service = _service(tmp_path)
    library = service.register_roots(service.empty_library(), [first_root, second_root])
    library = service.rescan(library).library

    first_save = service.save(library)
    first_bytes = service.path.read_bytes()
    load = service.load()
    second_save = service.save(load.library)  # type: ignore[arg-type]

    assert first_save.succeeded and second_save.succeeded and load.succeeded
    assert load.library == library
    assert service.path.read_bytes() == first_bytes
    document = json.loads(first_bytes)
    assert document["schema_version"] == LOCAL_APK_LIBRARY_SCHEMA_VERSION
    assert [item["path"] for item in document["roots"]] == sorted(
        [str(first_root.resolve()), str(second_root.resolve())], key=os.path.normcase
    )
    assert [item["artifact_sha256"] for item in document["artifacts"]] == sorted([_sha(b"z"), _sha(b"a")])


def test_unknown_schema_version_fails_safely(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.path.write_text(
        json.dumps({"schema_version": 99, "roots": [], "artifacts": [], "locations": []}),
        encoding="utf-8",
    )

    result = service.load()

    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.kind is LibraryLoadFailureKind.UNSUPPORTED_SCHEMA


def test_malformed_json_is_not_silently_overwritten(tmp_path: Path) -> None:
    service = _service(tmp_path)
    malformed = b'{"schema_version": 1, broken'
    service.path.write_bytes(malformed)

    result = service.load()

    assert not result.succeeded
    assert result.failure is not None
    assert result.failure.kind is LibraryLoadFailureKind.MALFORMED_JSON
    assert service.path.read_bytes() == malformed


def test_interrupted_atomic_replace_preserves_previous_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = _service(tmp_path)
    original = service.empty_library()
    assert service.save(original).succeeded
    original_bytes = service.path.read_bytes()
    changed = service.register_roots(original, [tmp_path / "root"])

    def failed_replace(_source: Path, _destination: Path) -> None:
        raise OSError("fixture")

    monkeypatch.setattr(library_service_module.os, "replace", failed_replace)
    result = service.save(changed)

    assert not result.succeeded
    assert service.path.read_bytes() == original_bytes
    assert not list(tmp_path.glob(f".{LIBRARY_FILENAME}.*.tmp"))


def test_recursive_discovery_extension_filtering_and_order(tmp_path: Path) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    paths = [root / "b.APK", nested / "a.apk", nested / "ignored.apks", root / "ignored.aab"]
    for index, path in enumerate(paths):
        path.write_bytes(bytes([index + 1]))
    calls: list[Path] = []

    def parser(path: Path) -> LocalArtifactParseResult:
        calls.append(path)
        return _fake_parser(path)

    service = _service(tmp_path, parser=parser)
    result = service.rescan(service.register_roots(service.empty_library(), [root]))

    assert [path.name for path in calls] == ["b.APK", "a.apk"]
    assert result.roots[0].status is LibraryRootScanStatus.COMPLETED
    assert result.roots[0].discovered_apks == 2
    assert len(result.library.artifacts) == 2


def test_directory_symlink_loop_is_not_followed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"one")
    original_scandir = library_service_module.os.scandir
    with original_scandir(root) as iterator:
        real_entries = list(iterator)

    class LinkStat:
        st_mode = stat.S_IFLNK
        st_file_attributes = 0

    class LinkEntry:
        name = "loop"
        path = str(root / "loop")

        @staticmethod
        def stat(*, follow_symlinks: bool = True) -> LinkStat:
            assert not follow_symlinks
            return LinkStat()

    class Entries:
        def __enter__(self):
            return iter([*real_entries, LinkEntry()])

        def __exit__(self, *_args: object) -> None:
            return None

    scans: list[Path] = []

    def guarded_scandir(path: str | os.PathLike[str]):
        scans.append(Path(path))
        if Path(path) != root:
            raise AssertionError("The directory link was followed")
        return Entries()

    monkeypatch.setattr(library_service_module.os, "scandir", guarded_scandir)
    service = _service(tmp_path)
    result = service.rescan(service.register_roots(service.empty_library(), [root]))

    assert result.roots[0].discovered_apks == 1
    assert len(result.library.locations) == 1
    assert scans == [root]


def test_bad_file_and_partial_parser_failure_keep_valid_artifacts(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "good.apk").write_bytes(b"good")
    (root / "bad.apk").write_bytes(b"bad")
    (root / "unreadable.apk").write_bytes(b"unreadable")
    service = _service(tmp_path)

    result = service.rescan(service.register_roots(service.empty_library(), [root]))

    assert len(result.library.artifacts) == 1
    assert len(result.issues) == 2
    assert all(issue.kind is LibraryScanIssueKind.PARSER_FAILURE for issue in result.issues)
    assert {issue.parser_failure_kind for issue in result.issues} == {
        LocalArtifactFailureKind.MALFORMED_ARCHIVE.value,
        LocalArtifactFailureKind.IO_ERROR.value,
    }
    assert result.roots[0].status is LibraryRootScanStatus.COMPLETED


def test_inaccessible_directory_is_partial_and_preserves_previous_location(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    nested = root / "nested"
    nested.mkdir(parents=True)
    apk = nested / "one.apk"
    apk.write_bytes(b"one")
    service = _service(tmp_path)
    library = _scan(service, root)
    original_scandir = library_service_module.os.scandir

    def guarded_scandir(path: str | os.PathLike[str]):
        if Path(path) == nested:
            raise PermissionError("fixture")
        return original_scandir(path)

    monkeypatch.setattr(library_service_module.os, "scandir", guarded_scandir)
    result = service.rescan(library)

    assert result.roots[0].status is LibraryRootScanStatus.PARTIAL
    assert result.issues[0].kind is LibraryScanIssueKind.DIRECTORY_INACCESSIBLE
    assert result.library.locations[0].present


def test_same_sha_at_two_paths_is_one_artifact_with_two_locations(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"same")
    (root / "two.apk").write_bytes(b"same")
    service = _service(tmp_path)

    library = _scan(service, root)

    assert len(library.artifacts) == 1
    assert len(library.locations) == 2
    assert {location.artifact_sha256 for location in library.locations} == {_sha(b"same")}
    assert all(location.present for location in library.locations)


def test_same_package_with_different_sha_values_remains_distinct(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"shared-one")
    (root / "two.apk").write_bytes(b"shared-two")
    service = _service(tmp_path)

    library = _scan(service, root)

    assert len(library.artifacts) == 2
    assert {artifact.package_id for artifact in library.artifacts} == {"com.example.shared"}
    assert len({artifact.artifact_sha256 for artifact in library.artifacts}) == 2


def test_repeated_unchanged_rescan_is_idempotent(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"one")
    service = _service(tmp_path)
    first = _scan(service, root)

    second = service.rescan(first).library

    assert second == first


def test_new_path_with_existing_sha_attaches_location(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    first_path = root / "one.apk"
    first_path.write_bytes(b"same")
    service = _service(tmp_path)
    library = _scan(service, root)
    (root / "two.apk").write_bytes(b"same")

    rescanned = service.rescan(library).library

    assert len(rescanned.artifacts) == 1
    assert len(rescanned.locations) == 2


def test_changed_file_at_same_path_points_to_new_artifact(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    path = root / "one.apk"
    path.write_bytes(b"old")
    service = _service(tmp_path)
    library = _scan(service, root)
    old_sha = library.artifacts[0].artifact_sha256
    path.write_bytes(b"new")

    rescanned = service.rescan(library).library

    assert {artifact.artifact_sha256 for artifact in rescanned.artifacts} == {
        old_sha,
        _sha(b"new"),
    }
    old_location = next(location for location in rescanned.locations if location.artifact_sha256 == old_sha)
    new_location = next(
        location for location in rescanned.locations if location.artifact_sha256 == _sha(b"new")
    )
    assert not old_location.present
    assert new_location.present
    assert old_location.path == new_location.path


@pytest.mark.parametrize("failure_mode", ["typed", "exception"])
def test_parser_rejection_invalidates_verified_association_at_same_path(
    tmp_path: Path,
    failure_mode: str,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    path = root / "one.apk"
    path.write_bytes(b"valid")

    def parser(candidate: Path) -> LocalArtifactParseResult:
        if candidate.read_bytes() == b"valid":
            return _fake_parser(candidate)
        if failure_mode == "exception":
            raise RuntimeError("unexpected parser fixture")
        return LocalArtifactParseResult(
            failure=LocalArtifactParseFailure(
                candidate,
                LocalArtifactFailureKind.MALFORMED_ARCHIVE,
                "Rejected changed APK fixture.",
            )
        )

    service = _service(tmp_path, parser=parser)
    library = _scan(service, root)
    old_sha = _sha(b"valid")
    assert library.artifacts[0].artifact_sha256 == old_sha
    assert library.locations[0].present
    assert [artifact.artifact_sha256 for artifact in service.auditable_artifacts(library)] == [
        old_sha
    ]
    path.write_bytes(b"rejected")

    result = service.rescan(library)

    assert result.roots[0].status is LibraryRootScanStatus.COMPLETED
    assert len(result.issues) == 1
    assert result.issues[0].kind is LibraryScanIssueKind.PARSER_FAILURE
    assert len(result.library.artifacts) == 1
    assert result.library.artifacts[0].artifact_sha256 == old_sha
    assert len(result.library.locations) == 1
    assert result.library.locations[0].artifact_sha256 == old_sha
    assert not result.library.locations[0].present
    assert service.auditable_artifacts(result.library) == ()


def test_missing_location_after_completed_scan_is_retained_not_present(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    path = root / "one.apk"
    path.write_bytes(b"one")
    service = _service(tmp_path)
    library = _scan(service, root)
    path.unlink()

    result = service.rescan(library)

    assert result.roots[0].status is LibraryRootScanStatus.COMPLETED
    assert len(result.library.artifacts) == 1
    assert len(result.library.locations) == 1
    assert not result.library.locations[0].present


def test_unavailable_root_does_not_mark_previous_locations_missing(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    path = root / "one.apk"
    path.write_bytes(b"one")
    service = _service(tmp_path)
    library = _scan(service, root)
    path.unlink()
    root.rmdir()

    result = service.rescan(library)

    assert result.roots[0].status is LibraryRootScanStatus.FAILED
    assert result.issues[0].kind is LibraryScanIssueKind.ROOT_UNAVAILABLE
    assert result.library.locations[0].present


def test_cancellation_keeps_coherent_partial_result_and_saved_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.apk").write_bytes(b"a")
    service = _service(tmp_path)
    original = _scan(service, root)
    assert service.save(original).succeeded
    original_bytes = service.path.read_bytes()
    (root / "b.apk").write_bytes(b"b")
    cancel = threading.Event()

    def progress(value) -> None:
        if value.current_path.name == "b.apk":
            cancel.set()

    result = service.rescan(original, cancel_event=cancel, progress_callback=progress)

    assert result.cancelled
    assert result.roots[0].status is LibraryRootScanStatus.CANCELLED
    assert len(result.library.artifacts) == 1
    assert result.library.locations[0].present
    assert service.path.read_bytes() == original_bytes
    assert service.load().library == original


def test_auditable_projection_returns_one_representative_per_sha(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "z.apk").write_bytes(b"same")
    (root / "a.apk").write_bytes(b"same")
    (root / "other.apk").write_bytes(b"shared-other")
    service = _service(tmp_path)
    library = _scan(service, root)

    artifacts = service.auditable_artifacts(library)

    assert len(artifacts) == 2
    same = next(artifact for artifact in artifacts if artifact.artifact_sha256 == _sha(b"same"))
    assert same.file_name == "a.apk"
    assert len({artifact.artifact_sha256 for artifact in artifacts}) == 2


def test_missing_artifact_is_excluded_from_auditable_projection(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    path = root / "one.apk"
    path.write_bytes(b"one")
    service = _service(tmp_path)
    library = _scan(service, root)
    path.unlink()
    library = service.rescan(library).library

    assert service.auditable_artifacts(library) == ()


def test_scan_has_no_store_provider_or_cache_interaction(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    (root / "one.apk").write_bytes(b"one")
    parser_calls: list[Path] = []

    def parser(path: Path) -> LocalArtifactParseResult:
        parser_calls.append(path)
        return _fake_parser(path)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Library scan must not call remote/cache services")

    import playstore_app_audit.services.alternative_distribution as alternative_distribution
    import playstore_app_audit.services.state as state
    from playstore_app_audit.services.play_store import PlayStoreService

    monkeypatch.setattr(PlayStoreService, "audit", forbidden)
    monkeypatch.setattr(alternative_distribution, "run_alternative_distribution_phase", forbidden)
    monkeypatch.setattr(state, "load_fresh_cache", forbidden)
    monkeypatch.setattr(state, "update_cache", forbidden)
    service = _service(tmp_path, parser=parser)

    result = service.rescan(service.register_roots(service.empty_library(), [root]))

    assert len(result.library.artifacts) == 1
    assert parser_calls == [(root / "one.apk").resolve()]


def test_paths_stay_in_dedicated_local_library_document(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    apk = root / "private-name.apk"
    apk.write_bytes(b"private")
    service = _service(tmp_path)
    library = _scan(service, root)

    assert service.save(library).succeeded
    document = json.loads(service.path.read_text(encoding="utf-8"))

    assert service.path.name == LIBRARY_FILENAME
    assert document["locations"][0]["path"] == str(apk.resolve())
    assert "store_result" not in document["artifacts"][0]
    assert "provider" not in document["artifacts"][0]


def test_duplicate_root_registration_is_normalised(tmp_path: Path) -> None:
    root = tmp_path / "root"
    service = _service(tmp_path)

    library = service.register_roots(service.empty_library(), [root, root / ".", str(root)])

    assert len(library.roots) == 1


def test_scan_issues_are_bounded(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    for index in range(5):
        (root / f"bad-{index}.apk").write_bytes(b"bad")
    service = LocalApkLibraryService(
        tmp_path / LIBRARY_FILENAME,
        parser=_fake_parser,
        clock=lambda: NOW,
        max_scan_issues=2,
    )

    result = service.rescan(service.register_roots(service.empty_library(), [root]))

    assert len(result.issues) == 2
    assert result.omitted_issue_count == 3
    assert result.roots[0].issue_count == 5

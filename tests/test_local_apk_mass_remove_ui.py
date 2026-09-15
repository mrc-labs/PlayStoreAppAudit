from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.local_apk_file_ops as file_ops
import playstore_app_audit.services.local_apk_mass_remove as mass_remove
import playstore_app_audit.services.local_package_metadata_cache as local_metadata_cache
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.main_window as main_window_ui
from playstore_app_audit.ui.local_apk_mass_remove_dialog import (
    LocalApkMassRemoveDialog,
)
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault(
        "QT_QPA_PLATFORM",
        "offscreen",
    )
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


@pytest.fixture
def window(
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> MainWindow:
    monkeypatch.setattr(
        local_metadata_cache,
        "app_data_dir",
        lambda: tmp_path,
    )

    settings: dict[str, object] = {
        "view_preset": "Basic",
        "recent_sources": [],
        "compare_previous": False,
        "cache_enabled": False,
        "store_language": "en",
        "store_workers": 4,
    }

    monkeypatch.setattr(
        state,
        "load_settings",
        lambda: dict(settings),
    )
    monkeypatch.setattr(
        state,
        "save_settings",
        lambda values: dict(values),
    )
    monkeypatch.setattr(
        compact_ui,
        "load_settings",
        lambda: dict(settings),
    )
    monkeypatch.setattr(
        compact_ui,
        "save_settings",
        lambda values: dict(values),
    )
    monkeypatch.setattr(
        device_insights,
        "get_recent_sources",
        lambda: [],
    )

    created = MainWindow()
    yield created

    created.close()
    app.processEvents()


def _row(
    path: Path,
    relationship: str,
    *,
    package: str = "com.example.app",
    app_name: str = "Example App",
    sha: str = "a" * 64,
) -> dict[str, object]:
    resolved = path.resolve(strict=False)

    return {
        "source_mode": local_apk_audit.SOURCE_MODE,
        "local_apk_location": str(resolved),
        "local_apk_file_name": resolved.name,
        "_provisional_key": str(resolved),
        "local_apk_version_comparison": relationship,
        "package_name": package,
        "app_name": app_name,
        "local_apk_label": app_name,
        "local_apk_sha256": sha,
        "store_url": "https://example.test/store-evidence",
    }


def _install_rows(
    window: MainWindow,
    rows: list[dict[str, object]],
    candidates: tuple[Path, ...] | None = None,
) -> None:
    if candidates is None:
        candidates = tuple(
            Path(
                str(row["local_apk_location"])
            ).resolve(strict=False)
            for row in rows
        )

    window._local_apk_candidates = candidates
    window.source_mode = local_apk_audit.SOURCE_MODE
    window.current_rows = rows

    window._sync_local_apk_file_mutation_views(
        candidates[0] if candidates else None
    )


class _AcceptedDialog:
    def __init__(
        self,
        _parent,
        plan,
    ) -> None:
        self.plan = plan

    def exec(self):
        return QDialog.DialogCode.Accepted


class _RejectedDialog:
    def __init__(
        self,
        _parent,
        plan,
    ) -> None:
        self.plan = plan

    def exec(self):
        return QDialog.DialogCode.Rejected


def test_preview_is_read_only_and_shows_blocked_entries(
    app: QApplication,
    tmp_path: Path,
) -> None:
    runnable = tmp_path / "runnable.apk"
    missing = tmp_path / "missing.apk"

    runnable.write_bytes(b"package")

    plan = (
        mass_remove.plan_local_package_mass_remove(
            [
                _row(runnable, "Outdated"),
                _row(missing, "Outdated"),
            ],
            (runnable, missing),
            mass_remove.MassRemoveTarget.OUTDATED,
        )
    )

    dialog = LocalApkMassRemoveDialog(
        None,
        plan,
    )

    dialog.show()
    app.processEvents()

    assert plan.runnable_count == 1
    assert plan.blocked_count == 1
    assert dialog.preview_table.rowCount() == 2
    assert "Selected: 1" in dialog.counts_label.text()
    assert "Blocked: 1" in dialog.counts_label.text()
    assert dialog.remove_button.isEnabled()

    assert runnable.read_bytes() == b"package"
    assert not missing.exists()

    dialog.close()


def test_mass_remove_actions_are_strict_and_idle_only(
    window: MainWindow,
    tmp_path: Path,
) -> None:
    outdated = tmp_path / "outdated.apk"
    unknown = tmp_path / "unknown.apk"
    not_applicable = tmp_path / "na.apk"

    for path in (
        outdated,
        unknown,
        not_applicable,
    ):
        path.write_bytes(b"package")

    rows = [
        _row(outdated, "Outdated"),
        _row(unknown, "Unknown"),
        _row(not_applicable, "N/A"),
    ]

    _install_rows(window, rows)
    window._sync_action_availability()

    assert (
        window.file_mass_remove_outdated_action.isEnabled()
    )
    assert (
        window.file_mass_remove_unknown_action.isEnabled()
    )

    window._source_operation_active = True
    window._sync_action_availability()

    assert not (
        window.file_mass_remove_outdated_action.isEnabled()
    )
    assert not (
        window.file_mass_remove_unknown_action.isEnabled()
    )

    window._source_operation_active = False
    window.current_rows = [
        _row(not_applicable, "N/A")
    ]
    window._sync_action_availability()

    assert not (
        window.file_mass_remove_outdated_action.isEnabled()
    )
    assert not (
        window.file_mass_remove_unknown_action.isEnabled()
    )


def test_cancel_leaves_files_untouched(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "outdated.apk"
    source.write_bytes(b"package")

    _install_rows(
        window,
        [_row(source, "Outdated")],
    )

    monkeypatch.setattr(
        main_window_ui.mass_remove_ui,
        "LocalApkMassRemoveDialog",
        _RejectedDialog,
    )

    window._show_local_apk_mass_remove(
        mass_remove.MassRemoveTarget.OUTDATED
    )

    assert source.read_bytes() == b"package"
    assert window._local_apk_candidates == (
        source.resolve(),
    )


def test_first_confirmation_no_leaves_files_untouched(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "unknown.apk"
    source.write_bytes(b"package")

    _install_rows(
        window,
        [_row(source, "Unknown")],
    )

    monkeypatch.setattr(
        main_window_ui.mass_remove_ui,
        "LocalApkMassRemoveDialog",
        _AcceptedDialog,
    )
    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "question",
        lambda *_args, **_kwargs:
            main_window_ui.QMessageBox.StandardButton.No,
    )

    window._show_local_apk_mass_remove(
        mass_remove.MassRemoveTarget.UNKNOWN
    )

    assert source.read_bytes() == b"package"


def test_entire_source_requires_second_confirmation(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "outdated.apk"
    source.write_bytes(b"package")

    _install_rows(
        window,
        [_row(source, "Outdated")],
    )

    monkeypatch.setattr(
        main_window_ui.mass_remove_ui,
        "LocalApkMassRemoveDialog",
        _AcceptedDialog,
    )

    titles: list[str] = []

    def answer(
        _parent,
        title,
        _message,
        *_args,
        **_kwargs,
    ):
        titles.append(title)

        if len(titles) == 1:
            return (
                main_window_ui.QMessageBox.StandardButton.Yes
            )

        return main_window_ui.QMessageBox.StandardButton.No

    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "question",
        answer,
    )

    window._show_local_apk_mass_remove(
        mass_remove.MassRemoveTarget.OUTDATED
    )

    assert titles == [
        "Confirm Mass Remove",
        "Remove Entire Local APK Source?",
    ]
    assert source.read_bytes() == b"package"


def test_partial_source_remove_syncs_without_reaudit(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outdated = tmp_path / "outdated.apk"
    current = tmp_path / "current.apk"

    outdated.write_bytes(b"outdated")
    current.write_bytes(b"current")

    rows = [
        _row(
            outdated,
            "Outdated",
            package="com.example.outdated",
        ),
        _row(
            current,
            "Match",
            package="com.example.current",
        ),
    ]

    _install_rows(window, rows)

    monkeypatch.setattr(
        main_window_ui.mass_remove_ui,
        "LocalApkMassRemoveDialog",
        _AcceptedDialog,
    )
    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "question",
        lambda *_args, **_kwargs:
            main_window_ui.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        window,
        "_start_local_apk_audit",
        lambda: pytest.fail(
            "Mass Remove must not rerun the Store audit"
        ),
    )

    window._show_local_apk_mass_remove(
        mass_remove.MassRemoveTarget.OUTDATED
    )

    assert not outdated.exists()
    assert current.read_bytes() == b"current"

    assert window._local_apk_candidates == (
        current.resolve(),
    )
    assert len(window.current_rows) == 1
    assert (
        window.current_rows[0]["package_name"]
        == "com.example.current"
    )


def test_partial_failure_keeps_failed_duplicate_identity_row(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"

    first.write_bytes(b"first")
    second.write_bytes(b"second")

    rows = [
        _row(
            first,
            "Outdated",
            package="com.example.same",
            sha="f" * 64,
        ),
        _row(
            second,
            "Outdated",
            package="com.example.same",
            sha="f" * 64,
        ),
    ]

    _install_rows(window, rows)

    real_remove = file_ops.remove_local_package_file

    def injected_remove(path: str | Path):
        if Path(path).name == "first.apk":
            return file_ops.LocalPackageFileMutationResult(
                status=(
                    file_ops.LocalPackageFileMutationStatus.FAILED
                ),
                source=Path(path),
                message="Injected remove failure",
            )

        return real_remove(path)

    monkeypatch.setattr(
        mass_remove.file_ops,
        "remove_local_package_file",
        injected_remove,
    )
    monkeypatch.setattr(
        main_window_ui.mass_remove_ui,
        "LocalApkMassRemoveDialog",
        _AcceptedDialog,
    )
    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "question",
        lambda *_args, **_kwargs:
            main_window_ui.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "warning",
        lambda *_args, **_kwargs: None,
    )

    window._show_local_apk_mass_remove(
        mass_remove.MassRemoveTarget.OUTDATED
    )

    assert first.read_bytes() == b"first"
    assert not second.exists()

    assert window._local_apk_candidates == (
        first.resolve(),
    )
    assert len(window.current_rows) == 1

    assert (
        window.current_rows[0]["local_apk_location"]
        == str(first.resolve())
    )
    assert (
        window.current_rows[0]["package_name"]
        == "com.example.same"
    )
    assert (
        window.current_rows[0]["local_apk_sha256"]
        == "f" * 64
    )


def test_final_candidate_removal_clears_source_and_results(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "unknown.apk"
    source.write_bytes(b"package")

    _install_rows(
        window,
        [_row(source, "Unknown")],
    )

    monkeypatch.setattr(
        main_window_ui.mass_remove_ui,
        "LocalApkMassRemoveDialog",
        _AcceptedDialog,
    )
    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "question",
        lambda *_args, **_kwargs:
            main_window_ui.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        window,
        "_start_local_apk_audit",
        lambda: pytest.fail(
            "Final Mass Remove must not rerun Store audit"
        ),
    )

    window._show_local_apk_mass_remove(
        mass_remove.MassRemoveTarget.UNKNOWN
    )

    assert not source.exists()
    assert window._local_apk_candidates == ()
    assert window.current_rows == []
    assert window.source_mode is None
    assert (
        "No package files loaded"
        in window.source_label.text()
    )


def test_no_matching_files_never_reaches_confirmation(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "na.apk"
    source.write_bytes(b"package")

    _install_rows(
        window,
        [_row(source, "N/A")],
    )

    monkeypatch.setattr(
        main_window_ui.mass_remove_ui,
        "LocalApkMassRemoveDialog",
        _AcceptedDialog,
    )
    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "question",
        lambda *_args, **_kwargs: pytest.fail(
            "No matching files must not reach destructive "
            "confirmation"
        ),
    )

    window._show_local_apk_mass_remove(
        mass_remove.MassRemoveTarget.UNKNOWN
    )

    assert source.read_bytes() == b"package"

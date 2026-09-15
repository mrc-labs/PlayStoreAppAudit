from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog

import playstore_app_audit.services.device_insights as device_insights
import playstore_app_audit.services.local_apk_audit as local_apk_audit
import playstore_app_audit.services.local_apk_mass_rename as mass_rename
import playstore_app_audit.services.local_package_metadata_cache as local_metadata_cache
import playstore_app_audit.services.state as state
import playstore_app_audit.ui.compact_window as compact_ui
import playstore_app_audit.ui.main_window as main_window_ui
from playstore_app_audit.services.local_apk_file_ops import (
    LocalPackageFileMutationStatus,
)
from playstore_app_audit.ui.local_apk_mass_rename_dialog import (
    DEFAULT_MASS_RENAME_TEMPLATE,
    LocalApkMassRenameDialog,
)
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
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
    *,
    package: str = "com.example.app",
    app_name: str = "Example App",
    version: str = "1.0",
    sha: str = "a" * 64,
) -> dict[str, object]:
    resolved = path.resolve()

    return {
        "source_mode": local_apk_audit.SOURCE_MODE,
        "local_apk_location": str(resolved),
        "local_apk_file_name": resolved.name,
        "_provisional_key": str(resolved),
        "local_apk_label": app_name,
        "app_name": app_name,
        "package_name": package,
        "play_title": f"{app_name} Store",
        "local_apk_version_name": version,
        "local_apk_sha256": sha,
        "store_url": "https://example.test/store-evidence",
    }


def _install_rows(
    window: MainWindow,
    rows: list[dict[str, object]],
) -> None:
    paths = tuple(
        Path(str(row["local_apk_location"])).resolve()
        for row in rows
    )

    window._local_apk_candidates = paths
    window.source_mode = local_apk_audit.SOURCE_MODE
    window.current_rows = rows
    window._sync_local_apk_file_mutation_views(
        paths[0] if paths else None
    )


class _AcceptedMassRenameDialog:
    def __init__(
        self,
        _parent,
        rows,
    ) -> None:
        self.plan = (
            mass_rename.plan_local_package_mass_rename(
                rows,
                DEFAULT_MASS_RENAME_TEMPLATE,
            )
        )

    def exec(self):
        return QDialog.DialogCode.Accepted


class _RejectedMassRenameDialog:
    def __init__(
        self,
        _parent,
        _rows,
    ) -> None:
        pass

    def exec(self):
        return QDialog.DialogCode.Rejected


def test_dialog_shows_preview_counts_and_token_guidance(
    app: QApplication,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    dialog = LocalApkMassRenameDialog(
        None,
        [_row(source)],
    )

    dialog.show()
    app.processEvents()

    assert (
        dialog.template_edit.text()
        == DEFAULT_MASS_RENAME_TEMPLATE
    )
    assert "{packagename}" in dialog.token_label.text()
    assert "{category}" in dialog.token_label.text()
    assert dialog.preview_table.rowCount() == 1
    assert "Rename: 1" in dialog.counts_label.text()
    assert dialog.rename_button.isEnabled()

    dialog.template_edit.setText("{category}")
    app.processEvents()

    assert dialog.plan.has_blocking_issues
    assert not dialog.rename_button.isEnabled()
    assert "Invalid: 1" in dialog.counts_label.text()
    assert "Missing metadata" in (
        dialog.preview_table.item(0, 3).text()
    )

    dialog.close()


def test_mass_rename_action_requires_idle_local_physical_rows(
    window: MainWindow,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    rows = [_row(source)]
    _install_rows(window, rows)

    window._sync_action_availability()
    assert window.file_mass_rename_action.isEnabled()

    window._source_operation_active = True
    window._sync_action_availability()
    assert not window.file_mass_rename_action.isEnabled()

    window._source_operation_active = False
    window.source_mode = "file"
    window._sync_action_availability()
    assert not window.file_mass_rename_action.isEnabled()

    window.source_mode = local_apk_audit.SOURCE_MODE
    source.unlink()
    window._sync_action_availability()
    assert not window.file_mass_rename_action.isEnabled()


def test_mass_rename_dialog_cancel_does_not_mutate(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    _install_rows(window, [_row(source)])

    monkeypatch.setattr(
        main_window_ui.mass_rename_ui,
        "LocalApkMassRenameDialog",
        _RejectedMassRenameDialog,
    )

    window._show_local_apk_mass_rename()

    assert source.read_bytes() == b"package"
    assert window._local_apk_candidates == (
        source.resolve(),
    )


def test_mass_rename_confirmation_no_does_not_mutate(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.apk"
    source.write_bytes(b"package")

    _install_rows(window, [_row(source)])

    monkeypatch.setattr(
        main_window_ui.mass_rename_ui,
        "LocalApkMassRenameDialog",
        _AcceptedMassRenameDialog,
    )
    monkeypatch.setattr(
        main_window_ui.QMessageBox,
        "question",
        lambda *_args, **_kwargs:
            main_window_ui.QMessageBox.StandardButton.No,
    )

    window._show_local_apk_mass_rename()

    assert source.read_bytes() == b"package"
    assert not (
        tmp_path / "com.example.app_1.0.apk"
    ).exists()


def test_confirmed_mass_rename_updates_duplicate_physical_files(
    window: MainWindow,
    app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first_dir = tmp_path / "one"
    second_dir = tmp_path / "two"
    first_dir.mkdir()
    second_dir.mkdir()

    first = first_dir / "first.apk"
    second = second_dir / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    rows = [
        _row(
            first,
            package="com.example.same",
            app_name="Same App",
            sha="f" * 64,
        ),
        _row(
            second,
            package="com.example.same",
            app_name="Same App",
            sha="f" * 64,
        ),
    ]
    _install_rows(window, rows)

    monkeypatch.setattr(
        main_window_ui.mass_rename_ui,
        "LocalApkMassRenameDialog",
        _AcceptedMassRenameDialog,
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
            "Mass Rename must not rerun the Store audit"
        ),
    )

    window._show_local_apk_mass_rename()
    app.processEvents()

    first_destination = (
        first_dir / "com.example.same_1.0.apk"
    ).resolve()
    second_destination = (
        second_dir / "com.example.same_1.0.apk"
    ).resolve()

    assert not first.exists()
    assert not second.exists()

    assert first_destination.read_bytes() == b"first"
    assert second_destination.read_bytes() == b"second"

    assert window._local_apk_candidates == (
        first_destination,
        second_destination,
    )

    assert (
        window.current_rows[0]["local_apk_location"]
        == str(first_destination)
    )
    assert (
        window.current_rows[1]["local_apk_location"]
        == str(second_destination)
    )

    assert (
        window.current_rows[0]["local_apk_file_name"]
        == first_destination.name
    )
    assert (
        window.current_rows[1]["local_apk_file_name"]
        == second_destination.name
    )

    assert (
        window.current_rows[0]["store_url"]
        == "https://example.test/store-evidence"
    )
    assert (
        window.current_rows[1]["store_url"]
        == "https://example.test/store-evidence"
    )

    assert window.details_panel._row is not None
    assert (
        window.details_panel._row["local_apk_location"]
        == str(first_destination)
    )


def test_partial_result_sync_uses_reported_final_locations(
    window: MainWindow,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.apk"
    second = tmp_path / "second.apk"
    first.write_bytes(b"first")
    second.write_bytes(b"second")

    rows = [
        _row(first, package="com.example.one"),
        _row(second, package="com.example.two"),
    ]
    _install_rows(window, rows)

    first_source = first.resolve()
    second_source = second.resolve()
    first_destination = (
        tmp_path / "first-renamed.apk"
    ).resolve()
    second_destination = (
        tmp_path / "second-renamed.apk"
    ).resolve()

    first.rename(first_destination)

    result = mass_rename.MassRenameExecutionResult(
        status=mass_rename.MassRenameBatchStatus.PARTIAL,
        entries=(
            mass_rename.MassRenameExecutionEntry(
                source=first_source,
                destination=first_destination,
                status=LocalPackageFileMutationStatus.RENAMED,
                final_location=first_destination,
            ),
            mass_rename.MassRenameExecutionEntry(
                source=second_source,
                destination=second_destination,
                status=LocalPackageFileMutationStatus.FAILED,
                final_location=second_source,
                message="Injected failure",
            ),
        ),
        message="Partial test result",
    )

    window._sync_local_apk_mass_rename_result(result)

    assert window._local_apk_candidates == (
        first_destination,
        second_source,
    )
    assert (
        window.current_rows[0]["local_apk_location"]
        == str(first_destination)
    )
    assert (
        window.current_rows[1]["local_apk_location"]
        == str(second_source)
    )
    assert first_destination.read_bytes() == b"first"
    assert second.read_bytes() == b"second"

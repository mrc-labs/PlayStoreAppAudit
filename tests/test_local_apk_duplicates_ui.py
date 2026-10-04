from __future__ import annotations

import os
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QMessageBox
from test_local_apk_duplicates import row

from playstore_app_audit.services import device_insights, local_package_metadata_cache, state
from playstore_app_audit.services import local_apk_duplicates as duplicates
from playstore_app_audit.services import local_apk_file_ops as file_ops
from playstore_app_audit.ui import compact_window
from playstore_app_audit.ui import main_window as main_window_ui
from playstore_app_audit.ui.local_apk_duplicates_dialog import LocalApkDuplicatesDialog
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> MainWindow:
    settings = {
        "view_preset": "Basic",
        "recent_sources": [],
        "compare_previous": False,
        "cache_enabled": False,
    }
    for module in (state, compact_window):
        monkeypatch.setattr(module, "load_settings", lambda: dict(settings))
        monkeypatch.setattr(module, "save_settings", lambda values: dict(values))
    monkeypatch.setattr(local_package_metadata_cache, "app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(device_insights, "get_recent_sources", lambda: [])
    created = MainWindow()
    yield created
    created.close()
    app.processEvents()


@pytest.fixture
def copies(tmp_path: Path) -> list[Path]:
    paths = [tmp_path / f"copy-{index}.apk" for index in range(3)]
    for path in paths:
        path.write_bytes(b"identical package bytes")
    return paths


def install(window: MainWindow, paths: list[Path]) -> None:
    window.source_mode = "local_apk"
    window._local_apk_candidates = tuple(paths)
    window.current_rows = [row(path) for path in paths]
    window._sync_local_apk_file_mutation_views(paths[0])


def dialog_for(copies: list[Path]) -> LocalApkDuplicatesDialog:
    return LocalApkDuplicatesDialog(
        None, duplicates.analyze_local_apk_duplicates([row(path) for path in copies], copies)
    )


def select_dialog(monkeypatch: pytest.MonkeyPatch, selected: list[Path]) -> None:
    class AcceptedDialog:
        def __init__(self, _parent: MainWindow, review: duplicates.DuplicateReview) -> None:
            self.plan = duplicates.plan_duplicate_cleanup(
                duplicates.snapshot_duplicate_review(review), selected
            )

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(main_window_ui.duplicates_ui, "LocalApkDuplicatesDialog", AcceptedDialog)


def test_selection_starts_empty_all_invalid_n_minus_one_valid(app: QApplication, copies: list[Path]) -> None:
    dialog = dialog_for(copies)
    assert dialog.selected_paths() == ()
    assert not dialog.remove_button.isEnabled()
    dialog.accept()
    assert dialog.result() == QDialog.DialogCode.Rejected
    for index in range(3):
        dialog.exact_table.item(index, 0).setCheckState(Qt.CheckState.Checked)
    assert not dialog.remove_button.isEnabled()
    assert not dialog.plan.executable
    dialog.exact_table.item(2, 0).setCheckState(Qt.CheckState.Unchecked)
    assert dialog.remove_button.isEnabled()
    assert dialog.plan.selected_count == 2
    assert len(dialog.review.exact_groups[0].files) == 3
    for index, path in enumerate(copies):
        assert str(path) in dialog.exact_table.item(index, 5).text()
        assert dialog.review.exact_groups[0].sha256 == dialog.exact_table.item(index, 1).text()
    dialog.close()


@pytest.mark.parametrize("action", ["cancel", "close"])
def test_cancel_close_selected_copies_do_not_mutate(
    app: QApplication, copies: list[Path], action: str
) -> None:
    dialog = dialog_for(copies)
    dialog.exact_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    if action == "cancel":
        dialog.button_box.button(QDialogButtonBox.StandardButton.Cancel).click()
    else:
        dialog.close()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert all(path.read_bytes() == b"identical package bytes" for path in copies)


def test_versions_tab_read_only_and_no_cleanup_action(app: QApplication, copies: list[Path]) -> None:
    rows = [
        row(copies[0], sha="a" * 64),
        row(copies[1], sha="b" * 64),
        row(copies[2], sha="c" * 64, code=2, name="2.0"),
    ]
    dialog = LocalApkDuplicatesDialog(None, duplicates.analyze_local_apk_duplicates(rows, copies))
    assert dialog.versions_table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    findings = {
        dialog.versions_table.item(index, 0).text() for index in range(dialog.versions_table.rowCount())
    }
    assert findings == {"Same Version Variant", "Multiple Versions"}
    for index in range(dialog.versions_table.rowCount()):
        for column in range(dialog.versions_table.columnCount()):
            flags = dialog.versions_table.item(index, column).flags()
            assert not flags & Qt.ItemFlag.ItemIsUserCheckable
            assert not flags & Qt.ItemFlag.ItemIsEditable
    assert not dialog.remove_button.isEnabled()
    dialog.close()


def test_versions_tab_disables_previously_selected_cleanup(app: QApplication, copies: list[Path]) -> None:
    dialog = dialog_for(copies)
    dialog.exact_table.item(0, 0).setCheckState(Qt.CheckState.Checked)
    assert dialog.remove_button.isEnabled()
    dialog.tabs.setCurrentIndex(1)
    assert not dialog.remove_button.isEnabled()
    dialog.tabs.setCurrentIndex(0)
    assert dialog.remove_button.isEnabled()
    dialog.close()


@pytest.mark.parametrize(
    "busy_attr", ["_source_operation_active", "_local_apk_parse_active", "_audit_active"]
)
def test_menu_source_and_busy_aware_no_hash(
    window: MainWindow, copies: list[Path], busy_attr: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    install(window, copies)
    monkeypatch.setattr(
        duplicates.hashlib, "file_digest", lambda *_args: pytest.fail("Menu availability must not hash")
    )
    assert window.file_review_duplicates_action.isEnabled()
    setattr(window, busy_attr, True)
    window._sync_action_availability()
    assert not window.file_review_duplicates_action.isEnabled()
    setattr(window, busy_attr, False)
    window.source_mode = "app_list"
    window._sync_action_availability()
    assert not window.file_review_duplicates_action.isEnabled()
    window.source_mode = "local_apk"
    window._local_apk_candidates = (copies[0],)
    window._sync_action_availability()
    assert not window.file_review_duplicates_action.isEnabled()


def test_informational_findings_enable_menu(window: MainWindow, copies: list[Path]) -> None:
    install(window, copies)
    window.current_rows = [row(copies[0], sha="a" * 64), row(copies[1], sha="b" * 64)]
    window._sync_action_availability()
    assert window.file_review_duplicates_action.isEnabled()
    window.current_rows[1]["local_apk_version_code"] = 2
    window._sync_action_availability()
    assert window.file_review_duplicates_action.isEnabled()
    window.current_rows = [row(copies[0]), row(copies[0])]
    window._sync_action_availability()
    assert not window.file_review_duplicates_action.isEnabled()


def test_menu_placement(window: MainWindow) -> None:
    assert [
        "separator" if action.isSeparator() else action.text()
        for action in window.file_local_apk_menu.actions()
    ] == [
        "Choose Package File(s)…",
        "Choose Package Folder…",
        "separator",
        "Mass Rename…",
        "Review Duplicates…",
        "separator",
        "Remove All Outdated…",
        "Remove All Unknown…",
    ]


def test_review_rejection_does_not_confirm_or_mutate(
    window: MainWindow, copies: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    install(window, copies)
    monkeypatch.setattr(LocalApkDuplicatesDialog, "exec", lambda _self: QDialog.DialogCode.Rejected)
    monkeypatch.setattr(
        QMessageBox, "question", lambda *_args: pytest.fail("Cancelled review must not confirm")
    )
    window._show_local_apk_duplicates()
    assert all(path.exists() for path in copies)
    assert len(window.current_rows) == 3


def test_second_confirmation_no_preserves_files(
    window: MainWindow, copies: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    install(window, copies)
    select_dialog(monkeypatch, copies[:-1])
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.No)
    window._show_local_apk_duplicates()
    assert all(path.exists() for path in copies)
    assert len(window.current_rows) == 3


def test_cleanup_reconciles_success_only_and_preserves_distinct_rows(
    window: MainWindow, copies: list[Path], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    safe = [tmp_path / f"safe-{index}.apk" for index in range(2)]
    for path in safe:
        path.write_bytes(b"independent")
    install(window, [*copies, *safe])
    select_dialog(monkeypatch, [*copies[:-1], safe[0]])
    real_remove = file_ops.remove_local_package_file

    def remove(path: Path) -> file_ops.LocalPackageFileMutationResult:
        if path == copies[0]:
            return file_ops.LocalPackageFileMutationResult(
                file_ops.LocalPackageFileMutationStatus.FAILED, path, message="injected"
            )
        return real_remove(path)

    monkeypatch.setattr(file_ops, "remove_local_package_file", remove)
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    warnings: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda _parent, _title, text: warnings.append(text))
    monkeypatch.setattr(window, "_start_local_apk_audit", lambda: pytest.fail("Cleanup must not reaudit"))
    window._show_local_apk_duplicates()
    assert window._local_apk_candidates == (*copies, safe[1])
    assert [item["local_apk_location"] for item in window.current_rows] == [
        str(path) for path in (*copies, safe[1])
    ]
    assert window.model.rowCount() == 4
    assert window.table.currentIndex().isValid()
    assert "4 package file(s)" in window.source_label.text()
    assert "1 removed, 1 blocked/stale, 1 failed" in window.status_label.text()
    assert warnings and str(copies[0]) in warnings[0]
    assert not window._source_operation_active


def test_duplicate_cleanup_then_single_remove_final_copy(
    window: MainWindow, copies: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    install(window, copies)
    select_dialog(monkeypatch, copies[:-1])
    monkeypatch.setattr(QMessageBox, "question", lambda *_args: QMessageBox.StandardButton.Yes)
    window._show_local_apk_duplicates()
    assert window._local_apk_candidates == (copies[-1],)
    assert len(window.current_rows) == 1
    assert not window.file_review_duplicates_action.isEnabled()
    window._remove_local_package_row(window.current_rows[0])
    assert not copies[-1].exists()
    assert window._local_apk_candidates == ()
    assert window.current_rows == []
    assert window.source_mode is None


def test_changed_source_after_confirmation_aborts(
    window: MainWindow, copies: list[Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    install(window, copies)
    select_dialog(monkeypatch, copies[:-1])

    def answer(*_args: object) -> QMessageBox.StandardButton:
        window._local_apk_candidates = ()
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", answer)
    window._show_local_apk_duplicates()
    assert all(path.exists() for path in copies)

from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QObject, QPoint, Qt, QUrl, Slot
from PySide6.QtGui import QDesktopServices, QTextDocument
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QLabel

from playstore_app_audit.ui.about_updates import AboutUpdatesDialog
from playstore_app_audit.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    instance = QApplication.instance() or QApplication([])
    assert isinstance(instance, QApplication)
    return instance


def test_about_update_card_reserves_stable_status_space(app: QApplication) -> None:
    dialog = AboutUpdatesDialog()
    dialog.show()
    app.processEvents()
    try:
        card = dialog.findChild(QFrame, "AboutUpdateCard")
        assert card is not None
        assert dialog.update_action.sizePolicy().retainSizeWhenHidden()
        assert dialog.update_detail.minimumHeight() >= (
            dialog.update_detail.fontMetrics().lineSpacing() * 2
        )

        dialog.set_checking()
        app.processEvents()
        checking_height = card.height()

        dialog.set_up_to_date()
        app.processEvents()
        current_height = card.height()

        dialog.set_update_available("v2.0.0", "https://example.invalid/release")
        app.processEvents()
        update_height = card.height()

        assert checking_height == current_height == update_height
    finally:
        dialog.close()
        app.processEvents()


def test_about_sponsor_link_opens_only_on_explicit_click(app: QApplication) -> None:
    opened: list[str] = []

    class UrlHandler(QObject):
        @Slot(QUrl)
        def capture(self, url: QUrl) -> None:
            opened.append(url.toString())

    handler = UrlHandler()
    # Capture Qt's native external-link dispatch without launching a browser or networking.
    QDesktopServices.setUrlHandler("https", handler, "capture")
    dialog = AboutUpdatesDialog()
    try:
        sponsor = dialog.findChild(QLabel, "AboutSponsorLink")
        assert sponsor is not None
        assert sponsor.openExternalLinks()
        assert sponsor.wordWrap()
        assert sponsor.textFormat() == Qt.TextFormat.RichText
        assert sponsor.styleSheet() == ""
        assert sponsor.text().count("<a ") == 1
        assert (
            '<a href="https://github.com/sponsors/mrc-labs">'
            "Sponsor development on GitHub</a>"
        ) in sponsor.text()
        document = QTextDocument()
        document.setHtml(sponsor.text())
        assert document.toPlainText() == (
            "Enjoying Store App Audit? 🍺 Sponsor development on GitHub "
            "to help support testing and development tools."
        )

        dialog.show()
        app.processEvents()
        original_size = dialog.size()
        assert dialog.width() == 620
        assert dialog.height() == 500
        for update_state in (
            dialog.set_checking,
            dialog.set_up_to_date,
            lambda: dialog.set_update_available("v2.2.0", "https://example.invalid/release"),
            lambda: dialog.set_unavailable("The latest release could not be checked right now."),
        ):
            update_state()
            app.processEvents()
            assert dialog.size() == original_size
            assert sponsor.isVisible()
        assert opened == []

        # Click the linked words on the first line, using the native font's metrics.
        metrics = sponsor.fontMetrics()
        point = QPoint(
            metrics.horizontalAdvance("Enjoying Store App Audit? 🍺 ") + 20,
            metrics.height() // 2,
        )
        QTest.mouseClick(sponsor, Qt.MouseButton.LeftButton, pos=point)
        app.processEvents()
        assert opened == ["https://github.com/sponsors/mrc-labs"]
    finally:
        QDesktopServices.unsetUrlHandler("https")
        dialog.close()
        app.processEvents()


def test_audit_presets_stay_implemented_but_hidden_for_v2(app: QApplication) -> None:
    window = MainWindow()
    try:
        assert window.audit_profiles_menu.title() == "Audit Presets"
        assert not window.audit_profiles_menu.menuAction().isVisible()
    finally:
        window.close()
        app.processEvents()

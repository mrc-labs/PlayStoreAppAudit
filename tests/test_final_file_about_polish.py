from __future__ import annotations

import os

import pytest
from PySide6.QtWidgets import QApplication, QFrame

from playstore_app_audit.ui.about_updates import AboutUpdatesDialog


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

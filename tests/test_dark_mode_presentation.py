from __future__ import annotations

import os

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel

import playstore_app_audit.ui.base_window as base_ui
import playstore_app_audit.ui.table_window as table_ui
import playstore_app_audit.ui.theme as theme_ui


@pytest.fixture(scope="module")
def app() -> QApplication:
    os.environ.setdefault(
        "QT_QPA_PLATFORM",
        "offscreen",
    )
    instance = (
        QApplication.instance()
        or QApplication([])
    )
    assert isinstance(
        instance,
        QApplication,
    )
    return instance


def _palette(*, dark: bool) -> QPalette:
    palette = QPalette()

    if dark:
        window = "#1E2227"
        text = "#E6E9ED"
        base = "#22272D"
        button = "#2B3137"
        highlight = "#36546D"
        highlighted_text = "#F4F7F9"
    else:
        window = "#F5F7FA"
        text = "#20252B"
        base = "#FFFFFF"
        button = "#FFFFFF"
        highlight = "#DDEBF7"
        highlighted_text = "#18212A"

    for role, colour in (
        (QPalette.ColorRole.Window, window),
        (QPalette.ColorRole.WindowText, text),
        (QPalette.ColorRole.Base, base),
        (QPalette.ColorRole.Text, text),
        (QPalette.ColorRole.Button, button),
        (QPalette.ColorRole.ButtonText, text),
        (QPalette.ColorRole.Highlight, highlight),
        (
            QPalette.ColorRole.HighlightedText,
            highlighted_text,
        ),
    ):
        palette.setColor(
            role,
            QColor(colour),
        )

    return palette


def _relative_luminance(
    colour: QColor,
) -> float:
    channels = (
        colour.redF(),
        colour.greenF(),
        colour.blueF(),
    )

    linear = [
        channel / 12.92
        if channel <= 0.04045
        else (
            (channel + 0.055) / 1.055
        )
        ** 2.4
        for channel in channels
    ]

    return (
        0.2126 * linear[0]
        + 0.7152 * linear[1]
        + 0.0722 * linear[2]
    )


def _contrast_ratio(
    first: str,
    second: str,
) -> float:
    a = _relative_luminance(QColor(first))
    b = _relative_luminance(QColor(second))

    lighter = max(a, b)
    darker = min(a, b)

    return (
        lighter + 0.05
    ) / (
        darker + 0.05
    )


@pytest.mark.parametrize(
    "dark",
    [False, True],
)
def test_theme_detection_and_application_tokens(
    dark: bool,
) -> None:
    palette = _palette(dark=dark)

    assert (
        theme_ui.is_dark_palette(palette)
        is dark
    )

    colours = theme_ui.application_colours(
        palette
    )
    stylesheet = (
        theme_ui.application_stylesheet(
            palette
        )
    )

    assert colours.window in stylesheet
    assert colours.text in stylesheet
    assert colours.table in stylesheet
    assert colours.selection in stylesheet


@pytest.mark.parametrize(
    "dark",
    [False, True],
)
@pytest.mark.parametrize(
    "status_key",
    (
        "red",
        "orange",
        "yellow",
        "blue",
        "green",
        "purple",
    ),
)
def test_semantic_status_text_meets_aa_contrast(
    dark: bool,
    status_key: str,
) -> None:
    colours = (
        theme_ui.semantic_status_colours(
            status_key,
            _palette(dark=dark),
        )
    )

    assert (
        _contrast_ratio(
            colours.foreground,
            colours.background,
        )
        >= 4.5
    )


def test_dark_table_uses_theme_text_and_semantic_colours(
    app: QApplication,
) -> None:
    original = QPalette(app.palette())
    dark = _palette(dark=True)

    app.setPalette(dark)
    app.processEvents()

    model = table_ui.AuditTableModel()

    try:
        model.set_rows(
            [
                {
                    "source_mode": "device",
                    "criticality_key": "green",
                    "criticality": "Recent",
                    "package_name": "com.example.dark",
                    "version_comparison": "Outdated",
                }
            ]
        )

        package_index = model.index(
            0,
            model.columns.index(
                "package_name"
            ),
        )

        relation_index = model.index(
            0,
            model.columns.index(
                "version_comparison"
            ),
        )

        assert model.data(
            package_index,
            Qt.ItemDataRole.ForegroundRole,
        ) == theme_ui.text_colour(dark)

        assert model.data(
            package_index,
            Qt.ItemDataRole.BackgroundRole,
        ) == QColor(
            theme_ui.semantic_status_colours(
                "green",
                dark,
            ).background
        )

        assert model.data(
            relation_index,
            Qt.ItemDataRole.ForegroundRole,
        ) == QColor(
            theme_ui.semantic_status_colours(
                "orange",
                dark,
            ).foreground
        )

    finally:
        model.deleteLater()
        app.setPalette(original)
        app.processEvents()


def test_dark_semantic_label_uses_dark_status_foreground(
    app: QApplication,
) -> None:
    label = QLabel("Legacy target")
    dark = _palette(dark=True)
    label.setPalette(dark)

    try:
        assert (
            base_ui.apply_semantic_label_presentation(
                label,
                "compatibility_status",
                "Legacy target",
            )
        )

        expected = (
            theme_ui.semantic_status_colours(
                "orange",
                dark,
            ).foreground
        )

        assert (
            label.palette()
            .color(
                QPalette.ColorGroup.Active,
                QPalette.ColorRole.WindowText,
            )
            .name()
            .casefold()
            == expected.casefold()
        )

    finally:
        label.deleteLater()
        app.processEvents()


def test_filter_styles_have_distinct_dark_semantic_and_neutral_tokens() -> None:
    dark = _palette(dark=True)

    semantic = (
        theme_ui.semantic_filter_button_stylesheet(
            "red",
            dark,
        )
    )

    neutral = (
        theme_ui.neutral_filter_button_stylesheet(
            dark
        )
    )

    red = theme_ui.semantic_status_colours(
        "red",
        dark,
    )
    general = theme_ui.application_colours(
        dark
    )

    assert red.background in semantic
    assert red.foreground in semantic
    assert red.accent in semantic

    assert general.control in neutral
    assert general.text in neutral
    assert general.control_border in neutral

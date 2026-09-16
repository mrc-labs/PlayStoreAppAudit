from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True, slots=True)
class SemanticStatusColours:
    background: str
    foreground: str
    accent: str


@dataclass(frozen=True, slots=True)
class ApplicationColours:
    window: str
    text: str
    card: str
    card_border: str
    title: str
    subtitle: str
    section: str
    muted: str
    control: str
    control_border: str
    control_hover: str
    control_hover_border: str
    focus: str
    primary: str
    primary_hover: str
    progress: str
    progress_chunk: str
    table: str
    table_alternate: str
    table_border: str
    grid: str
    selection: str
    selection_text: str
    header: str
    header_text: str
    header_border: str
    warning_background: str
    warning_foreground: str
    warning_border: str
    error: str


LIGHT_STATUS_COLOURS = {
    "red": SemanticStatusColours(
        "#FDF3F3", "#7A3D3D", "#C94B4B"
    ),
    "orange": SemanticStatusColours(
        "#FFF7EE", "#76522E", "#D77A23"
    ),
    "yellow": SemanticStatusColours(
        "#FFFCEF", "#6E6229", "#C6A919"
    ),
    "blue": SemanticStatusColours(
        "#F0F7FC", "#355F78", "#3A84B8"
    ),
    "green": SemanticStatusColours(
        "#F2F9F3", "#396342", "#4D9560"
    ),
    "purple": SemanticStatusColours(
        "#F8F1FA", "#684A70", "#9A6BA7"
    ),
}

DARK_STATUS_COLOURS = {
    "red": SemanticStatusColours(
        "#3A2528", "#F5B3B3", "#E57373"
    ),
    "orange": SemanticStatusColours(
        "#3A2D22", "#F3C28F", "#E89B52"
    ),
    "yellow": SemanticStatusColours(
        "#383421", "#E6D77A", "#D9C451"
    ),
    "blue": SemanticStatusColours(
        "#22333D", "#9CCAE5", "#5BA5D5"
    ),
    "green": SemanticStatusColours(
        "#22352A", "#A7D8B2", "#67B97B"
    ),
    "purple": SemanticStatusColours(
        "#33283A", "#D2B4DC", "#A77AB6"
    ),
}

LIGHT_APPLICATION_COLOURS = ApplicationColours(
    window="#F5F7FA",
    text="#20252B",
    card="#FFFFFF",
    card_border="#E2E7EC",
    title="#18212A",
    subtitle="#64717D",
    section="#26323D",
    muted="#6F7C87",
    control="#FFFFFF",
    control_border="#CCD4DC",
    control_hover="#F2F6FA",
    control_hover_border="#AEBBC6",
    focus="#4A8BC2",
    primary="#236EA8",
    primary_hover="#1D6398",
    progress="#E9EEF3",
    progress_chunk="#4A8BC2",
    table="#FFFFFF",
    table_alternate="#FAFBFC",
    table_border="#DFE5EA",
    grid="#E7EBEF",
    selection="#DDEBF7",
    selection_text="#18212A",
    header="#F1F4F7",
    header_text="#35424E",
    header_border="#DDE3E8",
    warning_background="#FFF6E5",
    warning_foreground="#6B4A16",
    warning_border="#E9C77D",
    error="#B42318",
)

DARK_APPLICATION_COLOURS = ApplicationColours(
    window="#1E2227",
    text="#E6E9ED",
    card="#252A30",
    card_border="#3A424A",
    title="#F2F4F6",
    subtitle="#AAB4BE",
    section="#DCE2E7",
    muted="#A4AFB9",
    control="#2B3137",
    control_border="#4B5660",
    control_hover="#343B42",
    control_hover_border="#64717D",
    focus="#6CA6D1",
    primary="#2F79B5",
    primary_hover="#3C88C4",
    progress="#343B42",
    progress_chunk="#5A9CD1",
    table="#22272D",
    table_alternate="#272D33",
    table_border="#3D454D",
    grid="#343C44",
    selection="#36546D",
    selection_text="#F4F7F9",
    header="#2B3137",
    header_text="#DCE2E7",
    header_border="#424B54",
    warning_background="#3A3020",
    warning_foreground="#F2D293",
    warning_border="#8A6B32",
    error="#FF9C94",
)


def active_palette(
    palette: QPalette | None = None,
) -> QPalette:
    if palette is not None:
        return palette

    app = QApplication.instance()
    if isinstance(app, QApplication):
        return app.palette()

    return QPalette()


def is_dark_palette(
    palette: QPalette | None = None,
) -> bool:
    palette = active_palette(palette)
    window = palette.color(QPalette.ColorRole.Window)
    text = palette.color(QPalette.ColorRole.WindowText)

    # This works with native light/dark and high-contrast palettes without
    # relying on a platform-specific theme-name API.
    return window.lightnessF() < text.lightnessF()


def application_colours(
    palette: QPalette | None = None,
) -> ApplicationColours:
    return (
        DARK_APPLICATION_COLOURS
        if is_dark_palette(palette)
        else LIGHT_APPLICATION_COLOURS
    )


def semantic_status_colours(
    status_key: str,
    palette: QPalette | None = None,
) -> SemanticStatusColours:
    colours = (
        DARK_STATUS_COLOURS
        if is_dark_palette(palette)
        else LIGHT_STATUS_COLOURS
    )
    return colours.get(status_key, colours["blue"])


def text_colour(
    palette: QPalette | None = None,
) -> QColor:
    return QColor(application_colours(palette).text)


def selection_background_colour(
    palette: QPalette | None = None,
) -> QColor:
    return QColor(application_colours(palette).selection)


def selection_text_colour(
    palette: QPalette | None = None,
) -> QColor:
    return QColor(application_colours(palette).selection_text)


def selected_semantic_background(
    background: QColor,
    palette: QPalette | None = None,
) -> QColor:
    return (
        background.lighter(118)
        if is_dark_palette(palette)
        else background.darker(104)
    )


def semantic_filter_button_stylesheet(
    status_key: str,
    palette: QPalette | None = None,
) -> str:
    colours = semantic_status_colours(
        status_key,
        palette,
    )
    return (
        "QPushButton {"
        "min-height:29px;"
        "padding:1px 9px;"
        f"background:{colours.background};"
        f"color:{colours.foreground};"
        f"border:2px solid {colours.background};"
        "}"
        "QPushButton:hover {"
        f"border:2px solid {colours.accent};"
        "}"
        "QPushButton:checked {"
        f"border:2px solid {colours.accent};"
        "font-weight:650;"
        "}"
    )


def neutral_filter_button_stylesheet(
    palette: QPalette | None = None,
) -> str:
    colours = application_colours(palette)
    return (
        "QPushButton {"
        "min-height:29px;"
        "padding:1px 9px;"
        f"background:{colours.control};"
        f"color:{colours.text};"
        f"border:2px solid {colours.control_border};"
        "}"
        "QPushButton:hover {"
        f"background:{colours.control_hover};"
        f"border:2px solid {colours.control_hover_border};"
        "}"
        "QPushButton:checked {"
        f"border:2px solid {colours.muted};"
        "font-weight:650;"
        "}"
    )


def error_text_stylesheet(
    palette: QPalette | None = None,
) -> str:
    return (
        f"color:{application_colours(palette).error};"
        "font-weight:650;"
    )


def application_stylesheet(
    palette: QPalette | None = None,
) -> str:
    c = application_colours(palette)

    return f"""
QMainWindow, QWidget#Central {{
    background: {c.window};
    color: {c.text};
}}
QFrame#Card {{
    background: {c.card};
    border: 1px solid {c.card_border};
    border-radius: 12px;
}}
QFrame#SourceOption {{
    background: {c.control};
    border: 1px solid {c.card_border};
    border-radius: 8px;
}}
QLabel#Title {{
    font-size: 22pt;
    font-weight: 700;
    color: {c.title};
}}
QLabel#Subtitle {{
    color: {c.subtitle};
    font-size: 10pt;
}}
QLabel#SectionTitle {{
    font-size: 11pt;
    font-weight: 650;
    color: {c.section};
}}
QLabel#Muted {{
    color: {c.muted};
}}
QLabel#WarningBanner {{
    background: {c.warning_background};
    color: {c.warning_foreground};
    border: 1px solid {c.warning_border};
    padding: 10px;
    border-radius: 6px;
}}
QLineEdit, QSpinBox, QComboBox {{
    background: {c.control};
    color: {c.text};
    border: 1px solid {c.control_border};
    border-radius: 7px;
    min-height: 31px;
    padding: 2px 8px;
    selection-background-color: {c.primary};
    selection-color: white;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {c.focus};
}}
QPushButton, QToolButton {{
    background: {c.control};
    color: {c.text};
    border: 1px solid {c.control_border};
    border-radius: 7px;
    min-height: 32px;
    padding: 2px 12px;
}}
QPushButton:hover, QToolButton:hover {{
    background: {c.control_hover};
    border-color: {c.control_hover_border};
}}
QPushButton#Primary {{
    background: {c.primary};
    color: white;
    border: 1px solid {c.primary};
    font-weight: 650;
    min-height: 38px;
}}
QPushButton#Primary:hover {{
    background: {c.primary_hover};
}}
QPushButton#CriticalityButton {{
    min-height: 29px;
    padding: 1px 9px;
}}
QPushButton#CriticalityButton:checked {{
    border: 2px solid {c.muted};
    font-weight: 650;
}}
QCheckBox {{
    spacing: 7px;
}}
QProgressBar {{
    background: {c.progress};
    border: none;
    border-radius: 5px;
    height: 10px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {c.progress_chunk};
    border-radius: 5px;
}}
QTableView {{
    background: {c.table};
    color: {c.text};
    alternate-background-color: {c.table_alternate};
    border: 1px solid {c.table_border};
    border-radius: 8px;
    gridline-color: {c.grid};
    selection-background-color: {c.selection};
    selection-color: {c.selection_text};
}}
QHeaderView::section {{
    background: {c.header};
    color: {c.header_text};
    border: none;
    border-right: 1px solid {c.header_border};
    border-bottom: 1px solid {c.header_border};
    padding: 3px 7px;
    font-weight: 650;
}}
"""

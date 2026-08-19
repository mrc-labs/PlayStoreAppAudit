#!/usr/bin/env python3
"""Capture native/default versus Fusion Qt Widgets rendering for UI audits."""

from __future__ import annotations

import argparse
import json
import platform
from pathlib import Path

import PySide6
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollBar,
    QSlider,
    QStyleFactory,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from playstore_app_audit.ui.main_window import MainWindow


def _process_events(app: QApplication, cycles: int = 8) -> None:
    for _ in range(cycles):
        app.processEvents()


def _save_widget(widget: QWidget, path: Path, app: QApplication) -> None:
    widget.show()
    _process_events(app)
    pixmap = widget.grab()
    if pixmap.isNull():
        raise RuntimeError(f"Qt returned a null pixmap for {path.name}")
    if not pixmap.save(str(path), "PNG"):
        raise RuntimeError(f"Could not save {path}")
    if path.stat().st_size < 1_000:
        raise RuntimeError(f"Captured image is implausibly small: {path}")
    widget.close()
    _process_events(app, cycles=2)


def _build_plain_probe() -> QWidget:
    probe = QWidget()
    probe.setWindowTitle("Qt native-style probe")
    probe.resize(760, 620)

    root = QVBoxLayout(probe)
    root.setContentsMargins(24, 24, 24, 24)
    root.setSpacing(14)

    title = QLabel("Plain Qt Widgets style probe")
    font = title.font()
    font.setPointSize(font.pointSize() + 4)
    font.setBold(True)
    title.setFont(font)
    root.addWidget(title)

    description = QLabel(
        "No application QSS is applied here. This isolates the platform/default Qt style from Fusion."
    )
    description.setWordWrap(True)
    root.addWidget(description)

    group = QGroupBox("Common controls")
    form = QFormLayout(group)
    name_edit = QLineEdit("Example package filter")
    country = QComboBox()
    country.addItems(["Switzerland", "Italy", "United Kingdom"])
    form.addRow("Text field", name_edit)
    form.addRow("Combo box", country)
    root.addWidget(group)

    toggles = QHBoxLayout()
    checkbox = QCheckBox("Include system apps")
    checkbox.setChecked(True)
    radio_a = QRadioButton("Basic")
    radio_b = QRadioButton("Technical")
    radio_a.setChecked(True)
    toggles.addWidget(checkbox)
    toggles.addWidget(radio_a)
    toggles.addWidget(radio_b)
    toggles.addStretch(1)
    root.addLayout(toggles)

    actions = QHBoxLayout()
    primary = QPushButton("Run audit")
    secondary = QPushButton("Choose file")
    secondary.setEnabled(False)
    actions.addWidget(primary)
    actions.addWidget(secondary)
    actions.addStretch(1)
    root.addLayout(actions)

    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(64)
    root.addWidget(progress)

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(42)
    root.addWidget(slider)

    table = QTableWidget(3, 3)
    table.setHorizontalHeaderLabels(["Package", "Status", "Age"])
    rows = [
        ("com.example.current", "Current", "42 days"),
        ("com.example.aging", "Aging", "580 days"),
        ("com.example.removed", "Removed", "n/a"),
    ]
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            table.setItem(row_index, column_index, QTableWidgetItem(value))
    table.resizeColumnsToContents()
    table.setMinimumHeight(150)
    root.addWidget(table)

    scroll_row = QHBoxLayout()
    scroll_row.addWidget(QLabel("Explicit scrollbars"))
    horizontal = QScrollBar(Qt.Orientation.Horizontal)
    horizontal.setRange(0, 100)
    horizontal.setValue(35)
    vertical = QScrollBar(Qt.Orientation.Vertical)
    vertical.setRange(0, 100)
    vertical.setValue(60)
    vertical.setFixedHeight(72)
    scroll_row.addWidget(horizontal, 1)
    scroll_row.addWidget(vertical)
    root.addLayout(scroll_row)

    return probe


def _metadata(app: QApplication, requested_style: str) -> dict[str, object]:
    screen = app.primaryScreen()
    return {
        "requested_style": requested_style,
        "active_style": app.style().objectName(),
        "style_factory_keys": QStyleFactory.keys(),
        "qt_platform_plugin": QGuiApplication.platformName(),
        "qt_version": PySide6.__version__,
        "python_platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "application_font_family": app.font().family(),
        "screen": None
        if screen is None
        else {
            "name": screen.name(),
            "logical_dpi": screen.logicalDotsPerInch(),
            "device_pixel_ratio": screen.devicePixelRatio(),
            "geometry": [
                screen.geometry().x(),
                screen.geometry().y(),
                screen.geometry().width(),
                screen.geometry().height(),
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", choices=("native", "fusion"), required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    app = QApplication([])
    app.setApplicationName("Play Store App Audit UI Style Audit")

    default_style = app.style().objectName()
    if args.style == "fusion":
        fusion = QStyleFactory.create("Fusion")
        if fusion is None:
            raise RuntimeError("Qt Fusion style is unavailable")
        app.setStyle(fusion)

    metadata = _metadata(app, args.style)
    metadata["default_style_before_override"] = default_style

    probe = _build_plain_probe()
    _save_widget(probe, output_dir / f"plain-{args.style}.png", app)

    window = MainWindow()
    window.resize(1200, 760)
    _save_widget(window, output_dir / f"app-{args.style}.png", app)

    metadata_path = output_dir / f"metadata-{args.style}.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    print(metadata_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

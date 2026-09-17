from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtGui import QImage

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = (
    ROOT
    / "tools"
    / "generate_canonical_screenshots.py"
)

EXPECTED = {
    "store-app-audit-phone-maintenance.png": (
        1560,
        900,
    ),
    "store-app-audit-local-apk.png": (
        1560,
        900,
    ),
    "store-app-audit-changes-history.png": (
        820,
        720,
    ),
    "store-app-audit-mass-rename.png": (
        1080,
        640,
    ),
}


def _run_generator(
    output_dir: Path,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_SCALE_FACTOR"] = "1"
    env["QT_FONT_DPI"] = "96"

    return subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--output-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )


def test_canonical_screenshot_generator_is_offline_and_synthetic() -> None:
    source = GENERATOR.read_text(
        encoding="utf-8"
    )

    assert "requests.sessions.Session.request = _forbid_network" in source
    assert "main_window_ui.find_adb = lambda: None" in source

    assert "com.example.juniper.notes" in source
    assert "com.example.orbit.tasks" in source
    assert "com.example.cedar.maps" in source
    assert "com.example.lumen.reader" in source
    assert "com.example.harbor.weather" in source
    assert "com.example.mosaic.vault" in source

    forbidden = (
        "com.facebook.",
        "com.google.",
        "com.whatsapp",
        "com.instagram",
        "C:\\Users\\",
        "/home/",
    )

    for value in forbidden:
        assert value not in source


def test_generator_produces_complete_png_set(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"

    result = _run_generator(first)

    assert result.returncode == 0, (
        result.stdout,
        result.stderr,
    )

    assert {
        path.name
        for path in first.iterdir()
        if path.is_file()
    } == set(EXPECTED)

    for name, dimensions in EXPECTED.items():
        path = first / name

        # Headless/offscreen rendering is environment-dependent.
        # This smoke gate verifies a real non-empty PNG and exact geometry;
        # the committed Windows assets have the stronger visual/size gate.
        assert path.stat().st_size > 256

        image = QImage(str(path))

        assert not image.isNull()
        assert (
            image.width(),
            image.height(),
        ) == dimensions


def test_committed_canonical_images_match_contract() -> None:
    images = ROOT / "docs" / "images"

    for name, dimensions in EXPECTED.items():
        path = images / name

        assert path.is_file(), name
        assert path.stat().st_size > 8_000

        image = QImage(str(path))

        assert not image.isNull()
        assert (
            image.width(),
            image.height(),
        ) == dimensions

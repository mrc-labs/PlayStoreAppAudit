from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_native_codec_probe_repeats_and_exits_cleanly(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, '-c',
         'import sys;from pathlib import Path;'
         'sys.path.insert(0,sys.argv[1]);'
         'from PySide6.QtWidgets import QApplication;'
         'from complete_qt_imageformats import image_consumers;'
         'app=QApplication([]);'
         '[image_consumers(Path(sys.argv[2])) for _ in range(5)];'
         'print("codec repetitions complete",flush=True)',
         str(root / '.github/scripts'), str(tmp_path)],
        env={**os.environ, 'QT_QPA_PLATFORM': 'offscreen'},
        capture_output=True, text=True, timeout=60, check=False,
    )
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert 'codec repetitions complete' in result.stdout
    report = json.loads((tmp_path / 'image-format-consumers.json').read_text())
    assert {row['format'] for row in report['cases']} == {'webp', 'tiff', 'png', 'ico', 'bmp'}

"""Build raster app icons directly from the canonical vector artwork.

The committed SVG is the source of truth. The generated 256 px PNG bytes stay
embedded for packaged runtime use, without a loose SVG or Pillow dependency.
"""

from __future__ import annotations

import hashlib
import struct
import tempfile
from pathlib import Path

from playstore_app_audit._icon_data import ICON_PNG_BYTES as _ICON_BYTES

ICON_SOURCE = Path(__file__).resolve().parent / "assets" / "store_app_audit_icon.svg"
RUNTIME_ICON_SIZE = 256
WINDOWS_ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)
_ICON_HASH = hashlib.sha256(_ICON_BYTES).hexdigest()[:12]


def canonical_svg_source_bytes(source: Path = ICON_SOURCE) -> bytes:
    """Return checkout-EOL-independent LF bytes for SVG source identity hashing."""
    data = source.read_bytes()
    # Git may materialise text files with platform-specific line endings. Keep
    # generated source identity stable by hashing the repository-style LF form.
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def render_svg_png(size: int, source: Path = ICON_SOURCE) -> bytes:
    """Render a size-specific transparent PNG straight from the vector source."""
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    if size <= 0:
        raise ValueError("Icon size must be positive")
    renderer = QSvgRenderer(str(source))
    if not renderer.isValid():
        raise ValueError(f"Invalid SVG icon source: {source}")
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter)
    finally:
        painter.end()
    buffer = QBuffer()
    if not buffer.open(QIODevice.OpenModeFlag.WriteOnly) or not image.save(buffer, "PNG"):  # type: ignore[call-overload]
        raise OSError("Could not encode rendered app icon")
    return bytes(buffer.data().data())


def generate_app_icon(output: str | Path, size: int = RUNTIME_ICON_SIZE) -> Path:
    """Write a transparent PNG rendered directly from the canonical SVG."""
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(render_svg_png(size))
    return output


def ensure_runtime_icon() -> Path:
    """Materialise the embedded runtime PNG in the stable technical cache path."""
    target = Path(tempfile.gettempdir()) / "PlayStoreAppAudit" / f"app_icon_{_ICON_HASH}.png"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_ICON_BYTES)
    return target


def generate_windows_ico(directory: str | Path = ".") -> Path:
    """Assemble PNG-backed ICO entries, each rendered at its native size."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    images = [render_svg_png(size) for size in WINDOWS_ICON_SIZES]
    header = struct.pack("<HHH", 0, 1, len(images))
    entries = bytearray()
    offset = len(header) + 16 * len(images)
    for size, png in zip(WINDOWS_ICON_SIZES, images, strict=True):
        entries.extend(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(png), offset))
        offset += len(png)
    ico = directory / "app_icon.ico"
    ico.write_bytes(header + entries + b"".join(images))
    return ico

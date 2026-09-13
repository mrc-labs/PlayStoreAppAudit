from __future__ import annotations

import base64
import hashlib
import tempfile
from io import BytesIO
from pathlib import Path

# Project-owned Store App Package Audit icon. The mark intentionally avoids
# Google Play's triangular product-icon geometry and multicolour visual identity.
# Keeping the PNG embedded means source checkout and packaged runtime do not need
# an additional loose image asset.
_ICON_PNG_BASE64 = "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"

_ICON_BYTES = base64.b64decode(_ICON_PNG_BASE64)
_ICON_HASH = hashlib.sha256(_ICON_BYTES).hexdigest()[:12]


def generate_app_icon(output: str | Path, size: int = 256) -> Path:
    """Write the project-owned icon as a transparent PNG at the requested size."""
    from PIL import Image

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image = Image.open(BytesIO(_ICON_BYTES)).convert("RGBA")
    if image.size != (size, size):
        image = image.resize((size, size), Image.Resampling.LANCZOS)
    image.save(output, optimize=True)
    return output


def ensure_runtime_icon() -> Path:
    # Versioning prevents an older cached icon from surviving an app upgrade.
    target = (
        Path(tempfile.gettempdir())
        / "StoreAppPackageAudit"
        / f"app_icon_{_ICON_HASH}.png"
    )
    if not target.exists():
        generate_app_icon(target)
    return target


def generate_windows_ico(directory: str | Path = ".") -> Path:
    from PIL import Image

    directory = Path(directory)
    png = generate_app_icon(directory / "app_icon.png")
    ico = directory / "app_icon.ico"
    image = Image.open(png).convert("RGBA")
    image.save(
        ico,
        format="ICO",
        sizes=[
            (16, 16),
            (24, 24),
            (32, 32),
            (48, 48),
            (64, 64),
            (128, 128),
            (256, 256),
        ],
    )
    return ico

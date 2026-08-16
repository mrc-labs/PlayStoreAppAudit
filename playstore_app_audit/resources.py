from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from app_icon import _ICON_BYTES

_ICON_HASH = hashlib.sha256(_ICON_BYTES).hexdigest()[:12]


def ensure_runtime_icon() -> Path:
    """Materialise the embedded PNG without requiring Pillow at runtime."""
    target = Path(tempfile.gettempdir()) / "PlayStoreAppAudit" / f"app_icon_{_ICON_HASH}.png"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_ICON_BYTES)
    return target

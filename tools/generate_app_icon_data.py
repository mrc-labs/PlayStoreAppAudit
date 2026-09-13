"""Refresh the embedded runtime PNG from assets/store_app_audit_icon.svg."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from app_icon import (
    ICON_SOURCE,
    RUNTIME_ICON_SIZE,
    canonical_svg_source_bytes,
    render_svg_png,
)

OUTPUT = Path(__file__).resolve().parents[1] / "playstore_app_audit" / "_icon_data.py"


def main() -> None:
    png = render_svg_png(RUNTIME_ICON_SIZE)
    encoded = base64.b64encode(png).decode("ascii")
    lines = [encoded[index : index + 100] for index in range(0, len(encoded), 100)]
    source_hash = hashlib.sha256(canonical_svg_source_bytes()).hexdigest()
    body = (
        '"""Generated runtime icon data from assets/store_app_audit_icon.svg.\n\n'
        'Regenerate with: python -m tools.generate_app_icon_data\n"""\n\n'
        'from __future__ import annotations\n\nimport base64\n\n'
        f'ICON_SVG_SHA256 = "{source_hash}"\n'
        'ICON_PNG_BYTES = base64.b64decode(\n'
        + "".join(f'    "{line}"\n' for line in lines)
        + ')\n'
    )
    OUTPUT.write_text(body, encoding="utf-8", newline="\n")
    print(f"Wrote {OUTPUT} ({len(png)} PNG bytes)")


if __name__ == "__main__":
    main()

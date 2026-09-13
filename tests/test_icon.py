from __future__ import annotations

from io import BytesIO

from PIL import Image

from app_icon import _ICON_BYTES, generate_windows_ico
from playstore_app_audit.resources import ensure_runtime_icon


def test_embedded_icon_is_full_size_transparent_png() -> None:
    icon = Image.open(BytesIO(_ICON_BYTES)).convert("RGBA")

    assert icon.size == (256, 256)
    assert icon.getchannel("A").getbbox() == (13, 12, 242, 244)
    assert icon.getchannel("A").getextrema() == (0, 255)


def test_runtime_and_windows_icon_paths_are_valid(tmp_path) -> None:
    runtime_icon = ensure_runtime_icon()
    with Image.open(runtime_icon) as image:
        assert image.size == (256, 256)

    ico_path = generate_windows_ico(tmp_path)
    with Image.open(ico_path) as icon:
        assert (256, 256) in icon.ico.sizes()
        assert (16, 16) in icon.ico.sizes()

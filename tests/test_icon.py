from __future__ import annotations

from io import BytesIO

from PIL import Image

from app_icon import _ICON_BYTES, _ORIGINAL_ICON_BYTES, generate_windows_ico
from playstore_app_audit.resources import ensure_runtime_icon


def test_trimmed_icon_preserves_visible_artwork_pixels() -> None:
    original = Image.open(BytesIO(_ORIGINAL_ICON_BYTES)).convert("RGBA")
    trimmed = Image.open(BytesIO(_ICON_BYTES)).convert("RGBA")

    assert original.size == (256, 256)
    assert original.getchannel("A").getbbox() == (47, 36, 225, 216)
    assert trimmed.size == (200, 200)
    assert trimmed.getchannel("A").getbbox() == (11, 10, 189, 190)
    assert original.crop((47, 36, 225, 216)).tobytes() == trimmed.crop(
        (11, 10, 189, 190)
    ).tobytes()


def test_runtime_and_windows_icon_paths_are_valid(tmp_path) -> None:
    runtime_icon = ensure_runtime_icon()
    with Image.open(runtime_icon) as image:
        assert image.size == (200, 200)

    ico_path = generate_windows_ico(tmp_path)
    with Image.open(ico_path) as icon:
        assert (200, 200) in icon.ico.sizes()

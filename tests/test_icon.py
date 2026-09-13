from __future__ import annotations

import hashlib
import struct
from io import BytesIO
from xml.etree import ElementTree

from PIL import Image

from app_icon import (
    _ICON_BYTES,
    ICON_SOURCE,
    RUNTIME_ICON_SIZE,
    WINDOWS_ICON_SIZES,
    canonical_svg_source_bytes,
    generate_app_icon,
    generate_windows_ico,
)
from playstore_app_audit._icon_data import ICON_SVG_SHA256
from playstore_app_audit.resources import ensure_runtime_icon


def test_canonical_icon_is_true_vector_source() -> None:
    source = ICON_SOURCE.read_bytes()
    root = ElementTree.fromstring(source)

    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["viewBox"] == "0 0 256 256"
    assert hashlib.sha256(canonical_svg_source_bytes()).hexdigest() == ICON_SVG_SHA256
    assert not any(element.tag.rsplit("}", 1)[-1] == "image" for element in root.iter())
    assert b"data:image/" not in source.lower()
    assert any(element.tag.rsplit("}", 1)[-1] == "path" for element in root.iter())


def test_canonical_icon_source_hash_is_eol_stable(tmp_path) -> None:
    source = ICON_SOURCE.read_bytes()
    lf = source.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    lf_source = tmp_path / "lf.svg"
    crlf_source = tmp_path / "crlf.svg"
    lf_source.write_bytes(lf)
    crlf_source.write_bytes(crlf)

    assert canonical_svg_source_bytes(lf_source) == canonical_svg_source_bytes(crlf_source)
    assert hashlib.sha256(canonical_svg_source_bytes(lf_source)).hexdigest() == ICON_SVG_SHA256


def test_runtime_png_is_embedded_transparent_and_full_size(tmp_path) -> None:
    generated = generate_app_icon(tmp_path / "rendered.png", RUNTIME_ICON_SIZE)
    with Image.open(generated) as image:
        assert image.size == (RUNTIME_ICON_SIZE, RUNTIME_ICON_SIZE)
        assert image.getextrema()[3] == (0, 255)
    with Image.open(BytesIO(_ICON_BYTES)) as image:
        assert image.size == (RUNTIME_ICON_SIZE, RUNTIME_ICON_SIZE)
        assert image.getextrema()[3] == (0, 255)

    runtime_icon = ensure_runtime_icon()
    assert runtime_icon.parent.name == "PlayStoreAppAudit"
    assert runtime_icon.read_bytes() == _ICON_BYTES


def test_windows_ico_renders_every_size_directly_from_svg(tmp_path) -> None:
    # An unrelated old output cannot supply any of the ICO's new raster entries.
    old_png = tmp_path / "app_icon.png"
    old_png.write_bytes(b"stale raster")
    ico = generate_windows_ico(tmp_path)
    assert old_png.read_bytes() == b"stale raster"

    data = ico.read_bytes()
    reserved, icon_type, count = struct.unpack_from("<HHH", data)
    assert (reserved, icon_type, count) == (0, 1, len(WINDOWS_ICON_SIZES))
    sizes = []
    for index in range(count):
        width, height, _colors, _reserved, planes, depth, length, offset = struct.unpack_from(
            "<BBBBHHII", data, 6 + index * 16
        )
        size = width or 256
        assert size == (height or 256)
        assert (planes, depth) == (1, 32)
        with Image.open(BytesIO(data[offset : offset + length])) as image:
            assert image.size == (size, size)
            assert image.format == "PNG"
        sizes.append(size)
    assert tuple(sizes) == WINDOWS_ICON_SIZES

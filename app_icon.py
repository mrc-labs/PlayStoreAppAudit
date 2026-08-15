from __future__ import annotations

from pathlib import Path
import tempfile


def generate_app_icon(output: str | Path, size: int = 256) -> Path:
    """Generate the PlayStoreAppAudit icon as a compact Fluent-style PNG."""
    from PIL import Image, ImageDraw, ImageFilter

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    s = int(size)
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Rounded blue Fluent-style tile with a light-to-deep vertical gradient.
    bg = Image.new("RGBA", (s, s))
    px = bg.load()
    for y in range(s):
        t = y / max(s - 1, 1)
        for x in range(s):
            edge = abs(x - s / 2) / max(s / 2, 1)
            r = int(18 * (1 - t) + 4 * t)
            g = max(50, int((137 * (1 - t) + 73 * t) - 18 * edge))
            b = max(120, int((245 * (1 - t) + 200 * t) - 8 * edge))
            px[x, y] = (r, g, b, 255)

    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle((3, 3, s - 4, s - 4), radius=int(s * 0.19), fill=255)
    img.alpha_composite(Image.composite(bg, Image.new("RGBA", (s, s), (0, 0, 0, 0)), mask))
    d = ImageDraw.Draw(img)

    scale = s / 256.0
    def P(v: float) -> int:
        return int(round(v * scale))

    # Minimal Android cue behind the phone.
    green = (133, 229, 61, 255)
    d.pieslice((P(32), P(130), P(112), P(210)), 180, 360, fill=green)
    d.rectangle((P(32), P(170), P(112), P(200)), fill=green)
    d.line((P(44), P(139), P(37), P(127)), fill=green, width=max(2, P(5)))
    d.line((P(95), P(139), P(102), P(127)), fill=green, width=max(2, P(5)))
    d.ellipse((P(51), P(155), P(59), P(163)), fill=(15, 91, 141, 255))
    d.ellipse((P(83), P(155), P(91), P(163)), fill=(15, 91, 141, 255))

    # Phone shadow.
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle((P(72), P(29), P(177), P(225)), radius=P(22), fill=(0, 0, 0, 95))
    shadow = shadow.filter(ImageFilter.GaussianBlur(max(1, P(6))))
    img.alpha_composite(shadow)
    d = ImageDraw.Draw(img)

    # Phone.
    d.rounded_rectangle((P(70), P(24), P(178), P(222)), radius=P(23), fill=(137, 208, 255, 255))
    d.rounded_rectangle((P(76), P(30), P(172), P(216)), radius=P(18), fill=(6, 58, 137, 255))
    d.rounded_rectangle((P(111), P(35), P(137), P(39)), radius=P(2), fill=(43, 133, 222, 255))

    # Simplified Play-inspired mark.
    left = (P(96), P(67))
    centre = (P(123), P(102))
    top_right = (P(153), P(102))
    left_bottom = (P(96), P(137))
    upper = (P(145), P(83))
    lower = (P(145), P(120))
    d.polygon([left, top_right, left_bottom], fill=(34, 181, 247, 255))
    d.polygon([left, centre, upper], fill=(113, 226, 77, 255))
    d.polygon([upper, top_right, lower, centre], fill=(255, 220, 62, 255))
    d.polygon([left_bottom, centre, lower], fill=(47, 207, 106, 255))

    # Magnifier shadow.
    sh = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    shd = ImageDraw.Draw(sh)
    shd.ellipse((P(135), P(132), P(222), P(219)), fill=(0, 0, 0, 95))
    shd.line((P(204), P(202), P(235), P(235)), fill=(0, 0, 0, 95), width=max(4, P(18)))
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, P(4))))
    img.alpha_composite(sh)
    d = ImageDraw.Draw(img)

    # Magnifier + checklist.
    d.ellipse((P(130), P(126), P(220), P(216)), fill=(159, 220, 255, 255))
    d.ellipse((P(137), P(133), P(213), P(209)), fill=(8, 66, 150, 255))
    d.line((P(204), P(201), P(238), P(235)), fill=(121, 185, 244, 255), width=max(4, P(17)))
    d.line((P(206), P(203), P(238), P(235)), fill=(65, 148, 230, 255), width=max(3, P(11)))
    for y in (151, 171, 191):
        d.line((P(151), P(y), P(158), P(y + 6), P(168), P(y - 6)), fill=(123, 230, 70, 255), width=max(2, P(5)), joint="curve")
        d.rounded_rectangle((P(178), P(y - 2), P(201), P(y + 3)), radius=P(2), fill=(31, 170, 244, 255))

    d.rounded_rectangle((P(3), P(3), P(252), P(252)), radius=P(48), outline=(93, 196, 255, 180), width=max(1, P(2)))
    img.save(output, optimize=True)
    return output


def ensure_runtime_icon() -> Path:
    target = Path(tempfile.gettempdir()) / "PlayStoreAppAudit" / "app_icon.png"
    if not target.exists():
        generate_app_icon(target, 256)
    return target


def generate_windows_ico(directory: str | Path = ".") -> Path:
    from PIL import Image

    directory = Path(directory)
    png = generate_app_icon(directory / "app_icon.png", 256)
    ico = directory / "app_icon.ico"
    image = Image.open(png).convert("RGBA")
    image.save(ico, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    return ico

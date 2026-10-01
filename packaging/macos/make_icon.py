"""Draw Chronicle's app icon and write packaging/macos/Chronicle.icns (needs Pillow and macOS's iconutil), plus the
dashboard's icons for phones' home screens (src/chronicle/web/icon-*.png; without iconutil, only those).

    uv run --group build python packaging/macos/make_icon.py
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
WEB = HERE.parents[1] / "src" / "chronicle" / "web"
S = 1024
M, R = 100, 185  # macOS icon grid: an 824px rounded square centred in 1024
TOP, BOTTOM = (78, 150, 250), (22, 62, 168)  # the tile's blue, top to bottom


def _layer(box, radius, fill, angle=0.0, highlight=0):
    """One rounded glass sheet on its own layer, rotated about the icon's centre; `highlight` adds the lit top rim."""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.rounded_rectangle(box, radius, fill=fill)
    if highlight:
        x0, y0, x1, y1 = box
        d.rounded_rectangle((x0 + 3, y0 + 3, x1 - 3, y1 - 3), radius - 3, outline=(255, 255, 255, highlight), width=4)
    return layer.rotate(angle, resample=Image.BICUBIC, center=(S / 2, S / 2)) if angle else layer


def _shadow(box, radius, angle=0.0, alpha=90, blur=26, dy=18):
    x0, y0, x1, y1 = box
    return _layer((x0, y0 + dy, x1, y1 + dy), radius, (8, 20, 60, alpha), angle).filter(ImageFilter.GaussianBlur(blur))


def _gradient(size: int) -> Image.Image:
    grad = Image.new("RGBA", (size, size))
    gd = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / (size - 1)
        gd.line([(0, y), (size, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(TOP, BOTTOM)) + (255,))
    return grad


def phone_icon(icon: Image.Image) -> Image.Image:
    """The tile, full bleed: phones cut their own rounded shape and would fill transparent corners with black."""
    box = (M, M, S - M, S - M)
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(box, R, fill=255)
    base = _gradient(S - 2 * M)
    base.paste(icon.crop(box), (0, 0), mask.crop(box))
    return base.convert("RGB")


def write_web_icons(icon: Image.Image) -> None:
    phone = phone_icon(icon)
    for size in (180, 192, 512):  # iOS home screen; the web app manifest's two sizes
        phone.resize((size, size), Image.LANCZOS).save(WEB / f"icon-{size}.png", optimize=True)


def draw() -> Image.Image:
    """Chronicle in the Liquid Glass style: a stack of translucent session cards on a deep blue tile;
    the front card is a transcript (lines of text) with the latest session marked in amber."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # macOS icon grid: an 824px rounded square centred in 1024, with a soft drop shadow
    m, r = M, R
    tile = (m, m, S - m, S - m)
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((m, m + 14, S - m, S - m + 14), r, fill=(0, 0, 0, 110))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    # the tile: Chronicle blue, lighter at the top, with a soft glow in the upper left
    grad = _gradient(S)
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((60, -40, 700, 560), fill=(255, 255, 255, 70))
    grad.alpha_composite(glow.filter(ImageFilter.GaussianBlur(90)))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle(tile, r, fill=255)
    img.paste(grad, (0, 0), mask)
    rim = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(rim).rounded_rectangle((m + 2, m + 2, S - m - 2, S - m - 2), r - 2, outline=(255, 255, 255, 90), width=5)
    img.alpha_composite(rim)

    # three cards, back to front: the older sessions are frosted glass, the newest is nearly opaque
    card, cr = (262, 318, 762, 698), 64
    stack = [(-13.0, (-6, -40), (255, 255, 255, 70), 120), (-6.0, (0, -14), (255, 255, 255, 110), 150), (0.0, (8, 20), (255, 255, 255, 244), 0)]
    for angle, (dx, dy), fill, hi in stack:
        box = (card[0] + dx, card[1] + dy, card[2] + dx, card[3] + dy)
        img.alpha_composite(_shadow(box, cr, angle, alpha=70 if hi else 110))
        img.alpha_composite(_layer(box, cr, fill, angle, highlight=hi))
    # the front card's transcript: an amber dot for the latest session, then lines of text
    d = ImageDraw.Draw(img)
    x0, y0 = card[0] + 8, card[1] + 20
    ink, amber = (120, 142, 196, 255), (255, 164, 52, 255)
    d.ellipse((x0 + 66, y0 + 70, x0 + 128, y0 + 132), fill=amber)
    d.rounded_rectangle((x0 + 160, y0 + 83, x0 + 420, y0 + 119), 18, fill=ink)
    d.rounded_rectangle((x0 + 66, y0 + 176, x0 + 434, y0 + 212), 18, fill=(170, 186, 222, 255))
    d.rounded_rectangle((x0 + 66, y0 + 256, x0 + 330, y0 + 292), 18, fill=(170, 186, 222, 255))
    return img


def main() -> None:
    icon = draw()
    icon.save(HERE / "icon.png")
    # the dashboard's touch icon, and the Dock icon when the app runs from source (Chronicle.app uses the .icns)
    icon.resize((256, 256), Image.LANCZOS).save(WEB / "icon.png", optimize=True)
    write_web_icons(icon)
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "Chronicle.iconset"
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                px = size * scale
                name = f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"
                icon.resize((px, px), Image.LANCZOS).save(iconset / name)
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(HERE / "Chronicle.icns")], check=True)
    print(f"wrote {HERE / 'Chronicle.icns'} and {HERE / 'icon.png'}")


if __name__ == "__main__":
    if not shutil.which("iconutil"):
        write_web_icons(draw())
        raise SystemExit(f"iconutil not found (macOS only): wrote only the web icons in {WEB}")
    main()

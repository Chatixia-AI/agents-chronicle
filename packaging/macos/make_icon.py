"""Draw Chronicle's app icon and write packaging/macos/Chronicle.icns (needs Pillow and macOS's iconutil).

    uv run --group build python packaging/macos/make_icon.py
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
S = 1024


def draw() -> Image.Image:
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    # macOS icon grid: an 824px rounded square centred in 1024, with a soft drop shadow
    m, r = 100, 185
    shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((m, m + 14, S - m, S - m + 14), r, fill=(0, 0, 0, 110))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))

    top, bottom = (35, 48, 92), (17, 24, 48)
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        gd.line([(0, y), (S, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)) + (255,))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle((m, m, S - m, S - m), r, fill=255)
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    # a timeline: a vertical rule with session entries of varying length, the latest one highlighted
    x0 = 330
    d.rounded_rectangle((x0 - 9, 270, x0 + 9, 760), 9, fill=(120, 140, 200, 255))
    rows = [(300, 330, (205, 214, 240)), (410, 250, (205, 214, 240)), (520, 300, (205, 214, 240)),
            (630, 210, (255, 184, 76))]
    for y, length, color in rows:
        d.ellipse((x0 - 30, y - 30, x0 + 30, y + 30), fill=color + (255,), outline=(17, 24, 48, 255), width=10)
        d.rounded_rectangle((x0 + 70, y - 22, x0 + 70 + length, y + 22), 22, fill=color + (255,))
    return img


def main() -> None:
    icon = draw()
    icon.save(HERE / "icon.png")
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
        raise SystemExit("iconutil not found (macOS only)")
    main()

"""Render the Blueprint Cast loops (the website's and the dashboard's loading scenes) as animated WebP plus a still.

Each scene is a pure function of time in filing.html or scenes.html; this renders it at 24 fps in headless Chromium,
then encodes it at 16 fps, half the render size, so it stays sharp on a retina screen.

    uv run --no-project --with playwright --with pillow python packaging/icons3d/loops.py [out_dir] [scene ...]

Writes <out_dir>/<scene>.webp and <scene>-still.webp (default out_dir: packaging/icons3d/out). The website copies
them to public/media/cast/. Needs blueprint-cast.js beside this file (see README.md).
"""

import base64
import functools
import http.server
import json
import socket
import sys
import threading
from io import BytesIO
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = Path(__file__).parent
RENDER_FPS, OUT_FPS = 24, 16



class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # no line per request
        pass

def frames(page, spec: dict) -> list[Image.Image]:
    page.goto(f"{page.base}/{spec['page']}{'&' if '?' in spec['page'] else '?'}w={spec['render']}")
    page.wait_for_function("window.ready === true")
    loop = page.evaluate("LOOP")
    out = []
    for i in range(round(loop * RENDER_FPS)):
        url = page.evaluate("t => renderFrame(t)", i / RENDER_FPS)
        out.append(Image.open(BytesIO(base64.b64decode(url.split(",", 1)[1]))).convert("RGBA"))
    return out


def encode(src: list[Image.Image], spec: dict, out_dir: Path, name: str) -> None:
    size = tuple(spec["size"])
    n = round(len(src) / RENDER_FPS * OUT_FPS)
    ims = [src[round(i * len(src) / n) % len(src)].resize(size, Image.Resampling.LANCZOS) for i in range(n)]
    path = out_dir / f"{name}.webp"
    # lossy alpha keeps the soft shadows and costs a third of lossless; quality 70 is where artefacts stay invisible
    ims[0].save(path, "WEBP", save_all=True, append_images=ims[1:], duration=round(1000 / OUT_FPS), loop=0,
                quality=70, alpha_quality=40, method=6, minimize_size=True)
    still = src[round(spec["still"] * RENDER_FPS) % len(src)].resize(size, Image.Resampling.LANCZOS)
    still.save(out_dir / f"{name}-still.webp", "WEBP", quality=85, alpha_quality=60)
    print(f"{name}: {n} frames, {path.stat().st_size // 1024} KB")


def main() -> None:
    if not (HERE / "blueprint-cast.js").exists():
        raise SystemExit("blueprint-cast.js is missing: see packaging/icons3d/README.md")
    specs = json.loads((HERE / "loops.json").read_text())
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "out"
    names = sys.argv[2:] or list(specs)
    out_dir.mkdir(parents=True, exist_ok=True)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    handler = functools.partial(Quiet, directory=str(HERE))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
            page = browser.new_page()
            page.base = f"http://127.0.0.1:{port}"
            page.on("pageerror", lambda e: print("page error:", e))
            for name in names:
                encode(frames(page, specs[name]), specs[name], out_dir, name)
            browser.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()

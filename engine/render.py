"""The page capture every render and check uses: a headless browser at SIZE (1920x1080, 1080x1920 or 1080x1080)
that seeks window.seek(t) and screenshots losslessly. film.py blends and encodes."""
import io, os, pathlib
import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

W, H = map(int, os.environ.get("SIZE", "1920x1080").split("x"))
FLAGS = ["--force-color-profile=srgb", "--disable-lcd-text", "--font-render-hinting=none", "--disable-gpu",
         # one raster thread, no partial raster: without these, antialiased edges differ by 1-3 levels between runs
         "--num-raster-threads=1", "--disable-partial-raster", "--disable-gpu-rasterization", "--disable-zero-copy",
         # every compositor stage finishes before a screenshot: glyph edges differed 6 runs in 64 without it, 1 with (E16)
         "--run-all-compositor-stages-before-draw"]


class Renderer:
    def __init__(self, html):
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(args=FLAGS)
        self.page = self.browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        self.page.goto(pathlib.Path(html).resolve().as_uri())
        self.page.evaluate("document.fonts.ready")

    def shot(self, t):
        self.page.evaluate(f"window.seek({t!r})")
        return np.asarray(Image.open(io.BytesIO(self.page.screenshot(type="png"))).convert("RGB"), dtype=np.float32)

    def close(self):
        self.browser.close()
        self.pw.stop()


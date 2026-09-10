"""Generate brand images for Home Assistant / HACS.

Writes icon + logo variants under custom_components/codex_rates/brand/
per https://developers.home-assistant.io/docs/core/integration/brand_images/
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "custom_components" / "codex_rates" / "brand"
OUT.mkdir(parents=True, exist_ok=True)

BG = (15, 40, 48, 255)
ARC_DIM = (60, 110, 120, 255)
ARC_HOT = (72, 201, 176, 255)
NEEDLE = (240, 248, 250, 255)
BAR_DIM = (120, 170, 180, 255)


def _draw_mark(img: Image.Image, *, dark: bool = False) -> None:
    d = ImageDraw.Draw(img)
    size = img.size[0]
    bg = (8, 22, 28, 255) if dark else BG
    margin = max(8, size // 16)
    radius = max(16, size // 5)
    d.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=bg,
    )

    cx, cy = size // 2, size // 2 + size // 20
    r = int(size * 0.29)
    width = max(4, size // 14)
    d.arc([cx - r, cy - r, cx + r, cy + r], start=200, end=340, fill=ARC_DIM, width=width)
    d.arc([cx - r, cy - r, cx + r, cy + r], start=200, end=295, fill=ARC_HOT, width=width)

    ang = math.radians(295)
    nx = cx + int(math.cos(ang) * (r - size // 25))
    ny = cy + int(math.sin(ang) * (r - size // 25))
    needle_w = max(2, size // 50)
    hub = max(3, size // 36)
    d.line([(cx, cy), (nx, ny)], fill=NEEDLE, width=needle_w)
    d.ellipse([cx - hub, cy - hub, cx + hub, cy + hub], fill=NEEDLE)

    bar_y0 = int(size * 0.78)
    bar_y1 = bar_y0 + max(4, size // 25)
    gap = size // 16
    left0, left1 = int(size * 0.27), int(size * 0.47)
    right0, right1 = left1 + gap, int(size * 0.73)
    d.rounded_rectangle([left0, bar_y0, left1, bar_y1], radius=3, fill=ARC_HOT)
    d.rounded_rectangle([right0, bar_y0, right1, bar_y1], radius=3, fill=BAR_DIM)


def _icon(size: int, *, dark: bool = False) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    _draw_mark(img, dark=dark)
    return img


def _logo(width: int, height: int, *, dark: bool = False) -> Image.Image:
    """Wide logo: mark on the left, wordmark-style bars on the right."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    bg = (8, 22, 28, 255) if dark else BG
    d.rounded_rectangle([0, 0, width - 1, height - 1], radius=height // 5, fill=bg)

    mark = _icon(height, dark=dark)
    # Use only the inner mark without double padding — scale into left square.
    mark_box = height
    mark_resized = mark.resize((mark_box, mark_box), Image.Resampling.LANCZOS)
    img.alpha_composite(mark_resized, (0, 0))

    # Simple textless wordmark bars (no font dependency).
    x0 = int(height * 0.95)
    y_mid = height // 2
    d.rounded_rectangle(
        [x0, y_mid - height // 5, width - height // 6, y_mid - height // 12],
        radius=4,
        fill=NEEDLE,
    )
    d.rounded_rectangle(
        [x0, y_mid + height // 16, width - height // 3, y_mid + height // 5],
        radius=4,
        fill=ARC_HOT,
    )
    return img


def main() -> None:
    files = {
        "icon.png": _icon(256),
        "icon@2x.png": _icon(512),
        "dark_icon.png": _icon(256, dark=True),
        "dark_icon@2x.png": _icon(512, dark=True),
        "logo.png": _logo(512, 256),
        "logo@2x.png": _logo(1024, 512),
        "dark_logo.png": _logo(512, 256, dark=True),
        "dark_logo@2x.png": _logo(1024, 512, dark=True),
    }
    for name, image in files.items():
        path = OUT / name
        image.save(path, "PNG")
        print(f"wrote {path} {image.size}")


if __name__ == "__main__":
    main()

"""Generate brand/icon.png for HACS."""

from pathlib import Path
import math

from PIL import Image, ImageDraw

out = Path(__file__).resolve().parents[1] / "custom_components" / "codex_rates" / "brand"
out.mkdir(parents=True, exist_ok=True)

size = 512
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

margin = 32
d.rounded_rectangle(
    [margin, margin, size - margin, size - margin],
    radius=96,
    fill=(15, 40, 48, 255),
)

cx, cy = size // 2, size // 2 + 24
r = 150
d.arc([cx - r, cy - r, cx + r, cy + r], start=200, end=340, fill=(60, 110, 120, 255), width=36)
d.arc([cx - r, cy - r, cx + r, cy + r], start=200, end=295, fill=(72, 201, 176, 255), width=36)

ang = math.radians(295)
nx = cx + int(math.cos(ang) * (r - 20))
ny = cy + int(math.sin(ang) * (r - 20))
d.line([(cx, cy), (nx, ny)], fill=(240, 248, 250, 255), width=10)
d.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=(240, 248, 250, 255))

d.rounded_rectangle([140, 400, 240, 420], radius=6, fill=(72, 201, 176, 255))
d.rounded_rectangle([260, 400, 372, 420], radius=6, fill=(120, 170, 180, 255))

path = out / "icon.png"
img.save(path, "PNG")
print(f"wrote {path} {img.size}")

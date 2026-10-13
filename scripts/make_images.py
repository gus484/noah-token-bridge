"""Erzeugt noah_token_bridge/icon.png (128x128) und logo.png (Add-on-Store).

    pip install pillow
    python scripts/make_images.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "noah_token_bridge"
GREEN = (46, 160, 90, 255)
DARK = (28, 40, 51, 255)
WHITE = (255, 255, 255, 255)
SCALE = 4  # Zeichnen in 4-facher Groesse, danach verkleinern (glatte Kanten)


def battery(size: int) -> Image.Image:
    """Batterie mit Blitz auf transparentem Grund, size = Kantenlaenge in Pixeln."""
    s = size * SCALE
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = s / 100
    d.rounded_rectangle((6 * u, 6 * u, 94 * u, 94 * u), radius=20 * u, fill=DARK)
    d.rounded_rectangle((20 * u, 30 * u, 74 * u, 74 * u), radius=7 * u, outline=WHITE, width=int(4 * u))
    d.rounded_rectangle((76 * u, 44 * u, 84 * u, 60 * u), radius=2 * u, fill=WHITE)
    d.rounded_rectangle((25 * u, 35 * u, 69 * u, 69 * u), radius=4 * u, fill=GREEN)
    bolt = [(50, 36), (36, 54), (46, 54), (42, 68), (58, 48), (48, 48)]
    d.polygon([(x * u, y * u) for x, y in bolt], fill=WHITE)
    return img.resize((size, size), Image.LANCZOS)


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main() -> None:
    battery(128).save(OUT / "icon.png")

    w, h = 250, 100
    logo = Image.new("RGBA", (w * SCALE, h * SCALE), (0, 0, 0, 0))
    logo.paste(battery(h * SCALE), (0, 0))
    d = ImageDraw.Draw(logo)
    d.text((h * SCALE + 6 * SCALE, 22 * SCALE), "Noah", font=font(30 * SCALE), fill=DARK)
    d.text((h * SCALE + 6 * SCALE, 58 * SCALE), "Token Bridge", font=font(17 * SCALE), fill=GREEN)
    logo.resize((w, h), Image.LANCZOS).save(OUT / "logo.png")
    print("icon.png, logo.png geschrieben nach", OUT)


if __name__ == "__main__":
    main()

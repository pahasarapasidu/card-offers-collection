"""Builds every icon for Credit Card Offers LK from one design.

Run from the project folder (needs Pillow: pip install pillow):
    python tools/make_icons.py

Writes
  mobile/assets/icon.png                     full icon (iOS / store / fallback)
  mobile/assets/android-icon-background.png  gradient layer
  mobile/assets/android-icon-foreground.png  card + badge inside the adaptive safe zone
  mobile/assets/android-icon-monochrome.png  white silhouette for Android 13+ themed icons
  mobile/assets/favicon.png                  48 px
  web/icons/*.png                            website / home-screen icons
  tools/icon-preview.png                     the icon under different launcher shapes
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "mobile" / "assets"
WEB = ROOT / "web" / "icons"
S = 1024
SAFE = 0.58  # share of the canvas the mark may use (Android adaptive safe zone ~61%)

# Palette (same as the website and app's light "Indigo" look)
NAVY = (0x1E, 0x1B, 0x4B)      # deep indigo
BRAND = (0x4F, 0x46, 0xE5)     # modern indigo
BLUE = (0x7C, 0x3A, 0xED)      # violet end of the gradient
BADGE = (0xF9, 0x73, 0x16)   # coral orange % badge
CHIP_GOLD = (253, 224, 138)
GLOW = (221, 214, 254)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def background():
    bg = Image.new("RGB", (S, S))
    px = bg.load()
    for y in range(S):
        for x in range(S):
            t = (x + y) / (2 * S - 2)
            px[x, y] = lerp(NAVY, BRAND, t / 0.62) if t < 0.62 else lerp(BRAND, BLUE, (t - 0.62) / 0.38)
    glow = Image.new("L", (S, S), 0)
    ImageDraw.Draw(glow).ellipse((560, -260, 1300, 480), fill=95)
    glow = glow.filter(ImageFilter.GaussianBlur(120))
    return Image.composite(Image.new("RGB", (S, S), GLOW), bg, glow).convert("RGBA")


def mark():
    """Credit card + emerald % badge (with soft shadow) on a transparent canvas."""
    card = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    x0, y0, x1, y1 = 200, 320, 824, 712
    d.rounded_rectangle((x0, y0, x1, y1), radius=56, fill=(255, 255, 255, 255))
    d.rectangle((x0, y0 + 90, x1, y0 + 160), fill=NAVY + (255,))
    d.rounded_rectangle((x0 + 60, y0 + 220, x0 + 180, y0 + 300), radius=16, fill=CHIP_GOLD + (255,))
    d.rounded_rectangle((x0 + 60, y0 + 330, x0 + 360, y0 + 352), radius=11, fill=(203, 213, 225, 255))
    card = card.rotate(-8, resample=Image.BICUBIC, center=(512, 516))

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    shadow = card.split()[3].point(lambda a: int(a * 0.45)).filter(ImageFilter.GaussianBlur(28))
    out.paste((0, 0, 0, 255), (14, 30), shadow)
    out = Image.alpha_composite(out, card)

    badge = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    b = ImageDraw.Draw(badge)
    bx, by, r = 742, 300, 150
    b.ellipse((bx - r - 10, by - r - 10, bx + r + 10, by + r + 10), fill=(255, 255, 255, 255))
    b.ellipse((bx - r, by - r, bx + r, by + r), fill=BADGE + (255,))
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/segoeuib.ttf", 200)
    except OSError:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 200)
    b.text((bx, by + 6), "%", font=font, fill=(255, 255, 255, 255), anchor="mm")
    return Image.alpha_composite(out, badge)


def fit_center(layer, frac):
    """Crop a transparent layer to its content and centre it at `frac` of the canvas."""
    content = layer.crop(layer.getbbox())
    scale = int(S * frac) / max(content.size)
    content = content.resize((max(1, int(content.width * scale)), max(1, int(content.height * scale))), Image.LANCZOS)
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(content, ((S - content.width) // 2, (S - content.height) // 2), content)
    return out


def masked(img, shape, size):
    mk = Image.new("L", (size * 4, size * 4), 0)
    d = ImageDraw.Draw(mk)
    if shape == "circle":
        d.ellipse((0, 0, size * 4 - 1, size * 4 - 1), fill=255)
    elif shape == "squircle":
        d.rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), radius=size * 4 // 3, fill=255)
    else:
        d.rounded_rectangle((0, 0, size * 4 - 1, size * 4 - 1), radius=size * 4 // 8, fill=255)
    return mk.resize((size, size), Image.LANCZOS)


def main():
    bg = background()
    m = mark()
    fg = fit_center(m, SAFE)
    full = Image.alpha_composite(bg, fit_center(m, 0.80)).convert("RGB")
    layered = Image.alpha_composite(bg, fg).convert("RGB")   # mark kept inside the safe zone

    # Monochrome: white silhouette without the shadow, card details and % cut out.
    solid = m.split()[3].point(lambda a: 255 if a > 200 else 0)
    detail = m.convert("L").point(lambda v: 255 if v < 200 else 0)
    mono_alpha = Image.composite(Image.new("L", (S, S), 0), solid, detail)
    mono = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    mono.putalpha(mono_alpha)
    mono = fit_center(mono, SAFE)

    bg.convert("RGB").save(ASSETS / "android-icon-background.png")
    fg.save(ASSETS / "android-icon-foreground.png")
    mono.save(ASSETS / "android-icon-monochrome.png")
    full.save(ASSETS / "icon.png")
    full.resize((48, 48), Image.LANCZOS).save(ASSETS / "favicon.png")

    WEB.mkdir(parents=True, exist_ok=True)
    full.save(WEB / "icon-1024.png")
    full.resize((180, 180), Image.LANCZOS).save(WEB / "apple-touch-icon.png")
    full.resize((32, 32), Image.LANCZOS).save(WEB / "favicon-32.png")
    full.resize((192, 192), Image.LANCZOS).save(WEB / "icon-192.png")
    # 512 is also listed as "maskable" in the manifest, so keep the mark in the safe zone
    layered.resize((512, 512), Image.LANCZOS).save(WEB / "icon-512.png")

    P = 192
    sheet = Image.new("RGB", (P * 4 + 50, P + 20), (235, 236, 240))
    small = layered.resize((P, P), Image.LANCZOS)
    for i, shape in enumerate(["circle", "squircle", "square"]):
        sheet.paste(small, (10 + i * (P + 10), 10), masked(small, shape, P))
    themed = Image.alpha_composite(Image.new("RGBA", (S, S), (60, 70, 90, 255)), mono).resize((P, P), Image.LANCZOS)
    sheet.paste(themed, (10 + 3 * (P + 10), 10), masked(themed, "circle", P))
    sheet.save(ROOT / "tools" / "icon-preview.png")
    print("icons written")


if __name__ == "__main__":
    main()

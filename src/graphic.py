"""
graphic.py

Generates a simple, ORIGINAL data-card image (headline + key stat) using
Pillow. This is drawn from scratch — no third-party news photos, no coin
logos, no copyrighted material — so there's no copyright risk in using it
on every auto-post.
"""

import os
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 675
BG_COLOR = (11, 13, 18)
ACCENT = (245, 158, 11)
TEXT_COLOR = (244, 244, 245)
MUTED = (156, 163, 175)

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "generated")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _font(size, bold=False):
    # Falls back to Pillow's default bitmap font if no TTF is bundled.
    try:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(name, size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def make_card(headline: str, stat_label: str, stat_value: str, filename: str) -> str:
    """
    Creates a simple dark-mode data card:
      - headline (wrapped, top)
      - one highlighted stat (e.g. "-6.6%" / "24h move")
      - footer note

    Returns the saved file path.
    """
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    headline_font = _font(46, bold=True)
    stat_font = _font(64, bold=True)
    label_font = _font(24)
    footer_font = _font(20)

    margin = 60
    lines = _wrap_text(draw, headline, headline_font, WIDTH - 2 * margin)[:3]
    y = 80
    for line in lines:
        draw.text((margin, y), line, font=headline_font, fill=TEXT_COLOR)
        y += 60

    # Divider
    draw.line([(margin, y + 20), (WIDTH - margin, y + 20)], fill=(42, 46, 55), width=1)

    # Stat box
    box_top = y + 60
    draw.rounded_rectangle(
        [(margin, box_top), (margin + 360, box_top + 160)],
        radius=12,
        fill=(28, 32, 39),
        outline=(58, 63, 74),
        width=1,
    )
    draw.text(
        (margin + 30, box_top + 30),
        stat_value,
        font=stat_font,
        fill=ACCENT,
    )
    draw.text(
        (margin + 30, box_top + 110),
        stat_label,
        font=label_font,
        fill=MUTED,
    )

    # Footer
    draw.text(
        (margin, HEIGHT - 50),
        "Not financial advice · DYOR",
        font=footer_font,
        fill=(75, 85, 99),
    )

    path = os.path.join(OUTPUT_DIR, filename)
    img.save(path)
    return path

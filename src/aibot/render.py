from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BACKGROUND = (18, 28, 52)
TEXT = (255, 255, 255)
ACCENT = (120, 190, 255)
MARGIN = 80  # 描画領域の余白（検証用の余白 60px より広くとる）
MAX_LINES = 6
SIZES = range(88, 47, -4)


def _wrap(draw, text: str, font, max_width: int) -> list[str]:
    lines, cur = [], ""
    for ch in text:
        if draw.textlength(cur + ch, font=font) <= max_width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


def render_image(
    headline: str,
    source: str,
    out_path: Path,
    font_path: Path,
    width: int = 1080,
    height: int = 1350,
) -> None:
    img = Image.new("RGB", (width, height), BACKGROUND)
    draw = ImageDraw.Draw(img)
    max_w = width - MARGIN * 2

    # 収まる最大のフォントサイズを探す
    chosen = None
    for size in SIZES:
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap(draw, headline, font, max_w)
        if len(lines) <= MAX_LINES:
            chosen = (font, lines, size)
            break
    if chosen is None:  # それでも収まらなければ末尾を「…」で切る
        size = SIZES[-1]
        font = ImageFont.truetype(str(font_path), size)
        lines = _wrap(draw, headline, font, max_w)[:MAX_LINES]
        while draw.textlength(lines[-1] + "…", font=font) > max_w:
            lines[-1] = lines[-1][:-1]
        lines[-1] += "…"
        chosen = (font, lines, size)
    font, lines, size = chosen

    line_h = int(size * 1.45)
    y = (height - line_h * len(lines)) // 2
    for line in lines:
        draw.text((MARGIN, y), line, font=font, fill=TEXT)
        y += line_h

    label_font = ImageFont.truetype(str(font_path), 40)
    label = source
    while label and draw.textlength(label, font=label_font) > max_w:
        label = label[:-1]
    draw.text((MARGIN, MARGIN + 20), label, font=label_font, fill=ACCENT)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="JPEG", quality=92)

import io
from pathlib import Path

import pytest
from PIL import Image

from aibot.render import BACKGROUND, render_image

FONT = Path(__file__).parent.parent / "fonts" / "NotoSansJP-Bold.otf"
W, H, M = 1080, 1350, 60


def _render(tmp_path, headline, name="o.jpg"):
    out = tmp_path / name
    render_image(headline, "媒体A", out, FONT)
    return out


def test_output_is_jpeg_with_expected_size(tmp_path):
    im = Image.open(_render(tmp_path, "AIの新しい発表"))
    assert im.format == "JPEG" and im.size == (W, H)


@pytest.mark.parametrize("headline", ["あ" * 40, "長い見出し" * 40, "GPT-5 and " * 20])
def test_long_headline_stays_inside_margins(tmp_path, headline):
    im = Image.open(_render(tmp_path, headline)).convert("RGB")
    bands = [(0, 0, W, M), (0, H - M, W, H), (0, 0, M, H), (W - M, 0, W, H)]
    for box in bands:
        colors = im.crop(box).getcolors(maxcolors=1_000_000)
        # JPEG圧縮の揺れを許容して、背景色に近い画素だけであることを確認
        assert all(max(abs(c - b) for c, b in zip(rgb, BACKGROUND)) <= 6 for _, rgb in colors)


def test_mixed_text_renders(tmp_path):
    _render(tmp_path, "GPT-5 が登場 🚀 Claude 5")


def test_different_headlines_make_different_images(tmp_path):
    a = _render(tmp_path, "見出しその一", "a.jpg").read_bytes()
    b = _render(tmp_path, "見出しその二", "b.jpg").read_bytes()
    assert a != b

from pathlib import Path

from aibot.config import load_config
from aibot.models import Draft


def test_load_config_reads_feeds(tmp_path: Path):
    p = tmp_path / "c.toml"
    p.write_text(
        '[news]\nlookback_hours = 24\nmax_candidates = 15\n'
        '[[news.feeds]]\nname = "A"\nurl = "https://a.example/rss"\n'
        '[claude]\nmodel = "claude-sonnet-5-5"\n'
        '[image]\nwidth = 1080\nheight = 1350\n',
        encoding="utf-8",
    )
    c = load_config(p)
    assert c.feeds[0].name == "A"
    assert c.lookback_hours == 24
    assert c.model == "claude-sonnet-5-5"
    assert (c.image_width, c.image_height) == (1080, 1350)


def test_draft_json_roundtrip():
    d = Draft("見出し", "本文", "https://e.com/a", "媒体", "2026-11-09")
    text = d.to_json()
    assert "見出し" in text  # \u エスケープされない
    assert Draft.from_json(text) == d

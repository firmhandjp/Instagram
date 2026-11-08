from pathlib import Path

from aibot.history import load_posted, normalize_url, record_posted


def test_normalize_url_drops_tracking():
    assert normalize_url("https://Example.com/a/?utm_source=x&id=1#top") == "https://example.com/a?id=1"


def test_normalize_url_equal_after_trailing_slash():
    assert normalize_url("https://e.com/a/") == normalize_url("https://e.com/a")


def test_load_posted_missing_file_is_empty(tmp_path: Path):
    assert load_posted(tmp_path / "none.json") == set()


def test_record_and_load_posted(tmp_path: Path):
    p = tmp_path / "posted.json"
    record_posted(p, "https://e.com/a?utm_source=x", "2026-11-09T07:00:00+09:00")
    assert "https://e.com/a" in load_posted(p)

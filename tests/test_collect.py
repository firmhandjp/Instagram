from datetime import datetime, timezone
from pathlib import Path

import feedparser

from aibot.collect import fetch_articles, select_candidates
from aibot.config import Feed
from aibot.models import Article

NOW = datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc)
SAMPLE = Path(__file__).parent / "fixtures" / "sample.xml"


def _parse_sample(_url):
    return feedparser.parse(SAMPLE.read_text(encoding="utf-8"))


def test_fetch_filters_by_lookback():
    arts = fetch_articles([Feed("S", "u")], NOW, 24, fetch=_parse_sample)
    assert [a.title for a in arts] == ["新しい記事A", "新しい記事B"]  # 新しい順
    assert arts[0].source == "S"


def test_fetch_isolates_broken_feed():
    def fetch(url):
        if url == "bad":
            raise RuntimeError("boom")
        return _parse_sample(url)

    arts = fetch_articles([Feed("Bad", "bad"), Feed("Good", "good")], NOW, 24, fetch=fetch)
    assert len(arts) == 2


def test_fetch_handles_empty_feed():
    arts = fetch_articles([Feed("E", "u")], NOW, 24, fetch=lambda u: feedparser.parse("<rss/>"))
    assert arts == []


def _art(url):
    return Article("t", url, "s", "", NOW)


def test_select_excludes_posted_with_tracking_params():
    arts = [_art("https://e.com/a?utm_source=x"), _art("https://e.com/b")]
    out = select_candidates(arts, {"https://e.com/a"}, 10)
    assert [a.url for a in out] == ["https://e.com/b"]


def test_select_respects_limit():
    arts = [_art(f"https://e.com/{i}") for i in range(5)]
    assert len(select_candidates(arts, set(), 3)) == 3


def test_default_fetch_sends_user_agent_and_timeout(monkeypatch):
    import socket

    import aibot.collect as collect

    seen = {}
    real_parse = feedparser.parse

    def fake_parse(url, agent=None):
        seen["agent"] = agent
        seen["timeout"] = socket.getdefaulttimeout()
        return real_parse("<rss/>")

    monkeypatch.setattr(collect.feedparser, "parse", fake_parse)
    collect.default_fetch("https://x.example/rss")
    assert seen["agent"] and "Mozilla" in seen["agent"]
    assert seen["timeout"] == collect.FETCH_TIMEOUT
    assert socket.getdefaulttimeout() != collect.FETCH_TIMEOUT  # 後始末されている

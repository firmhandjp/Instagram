from __future__ import annotations

import socket
import sys
from datetime import datetime, timedelta, timezone

import feedparser

from .config import Feed
from .history import normalize_url
from .models import Article


FETCH_TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; aibot/0.1; +https://github.com)"


def default_fetch(url: str):
    """時間制限と User-Agent を付けて RSS を取得する（遅い・拒否する情報源で止まらないように）。"""
    old = socket.getdefaulttimeout()
    socket.setdefaulttimeout(FETCH_TIMEOUT)
    try:
        return feedparser.parse(url, agent=USER_AGENT)
    finally:
        socket.setdefaulttimeout(old)


def fetch_articles(
    feeds: list[Feed],
    now: datetime,
    lookback_hours: int,
    fetch=default_fetch,
) -> list[Article]:
    """各情報源から直近 lookback_hours 時間の記事を集める。壊れた情報源は飛ばす。"""
    since = now - timedelta(hours=lookback_hours)
    articles: list[Article] = []
    for feed in feeds:
        try:
            parsed = fetch(feed.url)
        except Exception as exc:  # 1つの情報源の失敗で全体を止めない
            print(f"情報源を取得できませんでした: {feed.name} ({type(exc).__name__})", file=sys.stderr)
            continue
        for e in parsed.entries:
            pp = getattr(e, "published_parsed", None)
            link = getattr(e, "link", None)
            title = getattr(e, "title", None)
            if not pp or not link or not title:
                continue
            published = datetime(*pp[:6], tzinfo=timezone.utc)  # feedparser は UTC で返す
            if published < since or published > now:
                continue
            articles.append(Article(title, link, feed.name, getattr(e, "summary", "") or "", published))
    return sorted(articles, key=lambda a: a.published, reverse=True)


def select_candidates(articles: list[Article], posted: set[str], limit: int) -> list[Article]:
    fresh = [a for a in articles if normalize_url(a.url) not in posted]
    return fresh[:limit]

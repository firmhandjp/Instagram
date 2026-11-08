from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_EXACT = {"fbclid", "gclid"}


def normalize_url(url: str) -> str:
    """追跡パラメータ・フラグメント・末尾スラッシュ・ホストの大文字小文字の違いをなくす。"""
    parts = urlsplit(url.strip())
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_EXACT
    ]
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8") or "[]")


def load_posted(path: Path) -> set[str]:
    return {normalize_url(item["url"]) for item in _read(path)}


def record_posted(path: Path, url: str, posted_at: str) -> None:
    items = _read(path)
    items.append({"url": normalize_url(url), "posted_at": posted_at})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

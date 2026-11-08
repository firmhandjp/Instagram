from __future__ import annotations

import json

from .models import Article, Draft

MAX_HEADLINE = 40
MAX_BODY = 600
MAX_CAPTION = 2200
MIN_TAGS, MAX_TAGS = 3, 10

SYSTEM_PROMPT = """あなたは企業のInstagram公式アカウントの編集者です。AI関連ニュースの候補から、
社外の読者にとって最も価値のある記事を1本選び、日本語で投稿文を作ります。

ルール:
- 記事にない数字や事実を足さない。不確かなことは書かない。
- 元の文章を写さない。自分の言葉で要約する。
- 見出しは40文字以内、本文は600文字以内、ハッシュタグは3〜10個（各 # で始める）。
- 出典はこちらで付けるので、本文には書かない。
- 次のJSONだけを返す: {"index": 選んだ記事の番号(0始まり), "headline": "...", "body": "...", "hashtags": ["#...", ...]}
"""


class DraftError(Exception):
    """Claude の返答が使えない（形式の誤り・長すぎるなど）。"""


def build_caption(body: str, hashtags: list[str], source: str, url: str) -> str:
    return "\n\n".join([body, f"出典: {source} {url}", " ".join(hashtags)])


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise DraftError("返答にJSONがありません")
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise DraftError("返答のJSONを読めません") from exc
    if not isinstance(data, dict):
        raise DraftError("返答のJSONの形が違います")
    return data


def _prompt(candidates: list[Article]) -> str:
    lines = ["候補:"]
    for i, a in enumerate(candidates):
        lines.append(f"[{i}] 媒体: {a.source}\n題名: {a.title}\n概要: {a.summary[:500]}")
    return "\n\n".join(lines)


def generate_draft(candidates: list[Article], client, model: str, date: str) -> Draft:
    resp = client.messages.create(
        model=model,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _prompt(candidates)}],
    )
    data = _extract_json(resp.content[0].text)

    for key in ("index", "headline", "body", "hashtags"):
        if key not in data:
            raise DraftError(f"項目がありません: {key}")
    index, headline, body, tags = data["index"], data["headline"], data["body"], data["hashtags"]

    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(candidates):
        raise DraftError("記事の番号が範囲外です")
    if not isinstance(headline, str) or not 1 <= len(headline.strip()) <= MAX_HEADLINE:
        raise DraftError("見出しの長さが不正です")
    if not isinstance(body, str) or not 1 <= len(body.strip()) <= MAX_BODY:
        raise DraftError("本文の長さが不正です")
    if (
        not isinstance(tags, list)
        or not MIN_TAGS <= len(tags) <= MAX_TAGS
        or not all(isinstance(t, str) and t.startswith("#") and len(t) > 1 and " " not in t for t in tags)
    ):
        raise DraftError("ハッシュタグが不正です")

    article = candidates[index]
    caption = build_caption(body.strip(), tags, article.source, article.url)
    if len(caption) > MAX_CAPTION:
        raise DraftError("解説文が長すぎます")
    return Draft(headline.strip(), caption, article.url, article.source, date)

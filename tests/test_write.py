import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from aibot.models import Article
from aibot.write import DraftError, build_caption, generate_draft

NOW = datetime(2026, 11, 9, tzinfo=timezone.utc)
ARTS = [
    Article("記事1", "https://e.com/1", "媒体A", "概要1", NOW),
    Article("記事2", "https://e.com/2", "媒体B", "概要2", NOW),
]
GOOD = {"index": 1, "headline": "見出しです", "body": "本文です。", "hashtags": ["#AI", "#ニュース", "#生成AI"]}


class FakeClient:
    def __init__(self, text):
        self.calls = []
        self.messages = SimpleNamespace(create=self._create)
        self._text = text

    def _create(self, **kw):
        self.calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(text=self._text)])


def _gen(payload, raw=None):
    text = raw if raw is not None else json.dumps(payload, ensure_ascii=False)
    return generate_draft(ARTS, FakeClient(text), "m", "2026-11-09"), None


def test_generate_draft_builds_caption_with_source():
    d, _ = _gen(GOOD)
    assert d.article_url == "https://e.com/2"
    assert d.source == "媒体B"
    assert "媒体B" in d.caption and "https://e.com/2" in d.caption
    assert d.headline == "見出しです" and d.date == "2026-11-09"


def test_caption_format():
    c = build_caption("本文", ["#AI", "#ニュース", "#生成AI"], "媒体A", "https://e.com/a")
    parts = c.split("\n\n")
    assert parts == ["本文", "出典: 媒体A https://e.com/a", "#AI #ニュース #生成AI"]


def test_accepts_json_with_surrounding_text():
    d, _ = _gen(None, raw="はい、結果です。\n" + json.dumps(GOOD, ensure_ascii=False) + "\n以上")
    assert d.headline == "見出しです"


def test_rejects_non_json():
    with pytest.raises(DraftError):
        _gen(None, raw="すみません、選べませんでした")


@pytest.mark.parametrize("missing", ["index", "headline", "body", "hashtags"])
def test_rejects_missing_field(missing):
    p = {k: v for k, v in GOOD.items() if k != missing}
    with pytest.raises(DraftError):
        _gen(p)


@pytest.mark.parametrize("idx", [-1, 2, 99, "0", None])
def test_rejects_index_out_of_range(idx):
    with pytest.raises(DraftError):
        _gen({**GOOD, "index": idx})


@pytest.mark.parametrize(
    "override",
    [
        {"headline": "あ" * 41},
        {"body": "あ" * 601},
        {"hashtags": ["#a", "#b"]},
        {"hashtags": [f"#t{i}" for i in range(11)]},
        {"hashtags": ["#a", "#b", "c"]},
        {"headline": ""},
    ],
)
def test_rejects_invalid_values(override):
    with pytest.raises(DraftError):
        _gen({**GOOD, **override})


def test_rejects_caption_over_2200(monkeypatch):
    # 本文上限(600)を満たしても全体が2200を超える場合を弾く（出典URLが極端に長い場合）
    long_arts = [Article("t", "https://e.com/" + "a" * 2300, "媒体", "s", NOW)]
    text = json.dumps({**GOOD, "index": 0}, ensure_ascii=False)
    with pytest.raises(DraftError):
        generate_draft(long_arts, FakeClient(text), "m", "2026-11-09")


def test_prompt_forbids_adding_facts():
    client = FakeClient(json.dumps(GOOD, ensure_ascii=False))
    generate_draft(ARTS, client, "m", "2026-11-09")
    system = client.calls[0]["system"]
    assert "記事にない数字や事実を足さない" in system
    assert "要約" in system and "写さない" in system

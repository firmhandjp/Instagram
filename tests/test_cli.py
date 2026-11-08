import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from aibot import cli
from aibot.instagram import InstagramError
from aibot.models import Article, Draft
from aibot.write import DraftError

REPO = Path(__file__).parent.parent
NOW = "2026-11-09T07:00:00+09:00"
DRAFT = Draft("見出し", "解説\n\n出典: 媒体 https://e.com/a\n\n#AI #a #b", "https://e.com/a", "媒体", "2026-11-09")
ART = Article("t", "https://e.com/a", "媒体", "s", datetime(2026, 11, 8, 22, tzinfo=timezone.utc))


@pytest.fixture
def root(tmp_path):
    shutil.copy(REPO / "config.toml", tmp_path / "config.toml")
    (tmp_path / "fonts").mkdir()
    shutil.copy(REPO / "fonts" / "NotoSansJP-Bold.otf", tmp_path / "fonts")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "posted.json").write_text("[]", encoding="utf-8")
    return tmp_path


def _env(root, **extra):
    return {
        "ANTHROPIC_API_KEY": "k",
        "INSTAGRAM_ACCESS_TOKEN": "OLD-TOKEN",
        "INSTAGRAM_USER_ID": "42",
        "GITHUB_REPOSITORY": "o/r",
        "GITHUB_OUTPUT": str(root / "out.txt"),
        "GITHUB_STEP_SUMMARY": str(root / "summary.md"),
        **extra,
    }


def _patch_draft(monkeypatch, articles, result):
    monkeypatch.setattr(cli, "fetch_articles", lambda *a, **k: articles)
    monkeypatch.setattr(cli, "make_client", lambda key: object())

    def gen(cands, client, model, date):
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(cli, "generate_draft", gen)


def test_draft_writes_files_and_outputs_date(root, monkeypatch):
    _patch_draft(monkeypatch, [ART], DRAFT)
    assert cli.main(["draft", "--now", NOW], env=_env(root), root=root) == 0
    assert Draft.from_json((root / "drafts/2026-11-09.json").read_text(encoding="utf-8")) == DRAFT
    assert Image.open(root / "drafts/2026-11-09.jpg").format == "JPEG"
    assert "date=2026-11-09" in (root / "out.txt").read_text()
    summary = (root / "summary.md").read_text(encoding="utf-8")
    assert "raw.githubusercontent.com/o/r/main/drafts/2026-11-09.jpg" in summary
    assert "解説" in summary


def test_draft_fails_when_no_candidates(root, monkeypatch):
    _patch_draft(monkeypatch, [], DRAFT)
    assert cli.main(["draft", "--now", NOW], env=_env(root), root=root) == 1
    assert not (root / "drafts").exists()


def test_draft_fails_when_draft_error(root, monkeypatch):
    _patch_draft(monkeypatch, [ART], DraftError("長すぎます"))
    assert cli.main(["draft", "--now", NOW], env=_env(root), root=root) == 1
    assert not (root / "drafts").exists()


def _write_draft(root):
    (root / "drafts").mkdir(exist_ok=True)
    (root / "drafts/2026-11-09.json").write_text(DRAFT.to_json(), encoding="utf-8")


def test_publish_records_history_after_success(root, monkeypatch):
    _write_draft(root)
    calls = []
    monkeypatch.setattr(cli, "publish_image", lambda *a: calls.append(a) or "p1")
    assert cli.main(["publish", "--date", "2026-11-09"], env=_env(root), root=root) == 0
    assert calls[0] == (
        "https://raw.githubusercontent.com/o/r/main/drafts/2026-11-09.jpg",
        DRAFT.caption,
        "42",
        "OLD-TOKEN",
    )
    recorded = json.loads((root / "data/posted.json").read_text(encoding="utf-8"))
    assert recorded[0]["url"] == "https://e.com/a"


def test_publish_does_not_record_on_failure(root, monkeypatch):
    _write_draft(root)

    def boom(*a):
        raise InstagramError("HTTP 400")

    monkeypatch.setattr(cli, "publish_image", boom)
    assert cli.main(["publish", "--date", "2026-11-09"], env=_env(root), root=root) == 1
    assert json.loads((root / "data/posted.json").read_text(encoding="utf-8")) == []


def test_publish_skips_already_posted_article(root, monkeypatch):
    _write_draft(root)
    (root / "data/posted.json").write_text(
        json.dumps([{"url": "https://e.com/a", "posted_at": NOW}]), encoding="utf-8"
    )
    monkeypatch.setattr(cli, "publish_image", lambda *a: pytest.fail("投稿してはいけない"))
    assert cli.main(["publish", "--date", "2026-11-09"], env=_env(root), root=root) == 0


def test_refresh_token_never_prints_token(root, monkeypatch, capsys):
    stored = []
    monkeypatch.setattr(cli, "refresh_token", lambda t: "BRAND-NEW-TOKEN")
    monkeypatch.setattr(cli, "store_secret", lambda name, value, env: stored.append((name, value)))
    assert cli.main(["refresh-token"], env=_env(root, GH_ADMIN_TOKEN="g"), root=root) == 0
    out = capsys.readouterr()
    assert stored == [("INSTAGRAM_ACCESS_TOKEN", "BRAND-NEW-TOKEN")]
    shown = out.out + out.err
    assert "BRAND-NEW-TOKEN" not in shown and "OLD-TOKEN" not in shown

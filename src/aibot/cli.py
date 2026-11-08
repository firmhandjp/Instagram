from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .collect import fetch_articles, select_candidates
from .config import load_config
from .history import load_posted, normalize_url, record_posted
from .instagram import InstagramError, publish_image, refresh_token
from .models import Draft
from .render import render_image
from .write import DraftError, generate_draft

JST = ZoneInfo("Asia/Tokyo")
FONT = "fonts/NotoSansJP-Bold.otf"


def make_client(api_key: str):
    import anthropic

    return anthropic.Anthropic(api_key=api_key)


def store_secret(name: str, value: str, env: dict) -> None:
    """gh secret set で保存する。値は標準入力で渡し、引数・出力には出さない。"""
    cmd = ["gh", "secret", "set", name]
    if env.get("GITHUB_REPOSITORY"):
        cmd += ["--repo", env["GITHUB_REPOSITORY"]]
    run_env = {**os.environ, "GH_TOKEN": env["GH_ADMIN_TOKEN"]}
    subprocess.run(cmd, input=value, text=True, capture_output=True, check=True, env=run_env)


def _image_url(env: dict, date: str) -> str:
    return f"https://raw.githubusercontent.com/{env['GITHUB_REPOSITORY']}/main/drafts/{date}.jpg"


def _append(env: dict, key: str, text: str) -> None:
    path = env.get(key)
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)


def cmd_draft(args, env: dict, root: Path) -> int:
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(JST)
    date = now.astimezone(JST).strftime("%Y-%m-%d")
    cfg = load_config(root / "config.toml")
    posted = load_posted(root / "data" / "posted.json")

    articles = fetch_articles(cfg.feeds, now.astimezone(timezone.utc), cfg.lookback_hours)
    candidates = select_candidates(articles, posted, cfg.max_candidates)
    if not candidates:
        print("投稿できる候補の記事がありません。", file=sys.stderr)
        return 1
    try:
        draft = generate_draft(candidates, make_client(env["ANTHROPIC_API_KEY"]), cfg.model, date)
    except DraftError as exc:
        print(f"下書きを作れませんでした: {exc}", file=sys.stderr)
        return 1

    out = root / "drafts"
    render_image(draft.headline, draft.source, out / f"{date}.jpg", root / FONT, cfg.image_width, cfg.image_height)
    (out / f"{date}.json").write_text(draft.to_json() + "\n", encoding="utf-8")

    _append(env, "GITHUB_OUTPUT", f"date={date}\n")
    _append(
        env,
        "GITHUB_STEP_SUMMARY",
        f"## 今日の下書き（{date}）\n\n![下書き画像]({_image_url(env, date)})\n\n"
        f"**見出し**: {draft.headline}\n\n```\n{draft.caption}\n```\n",
    )
    print(f"下書きを作りました: {date} / {draft.headline}")
    return 0


def cmd_publish(args, env: dict, root: Path) -> int:
    draft = Draft.from_json((root / "drafts" / f"{args.date}.json").read_text(encoding="utf-8"))
    history = root / "data" / "posted.json"
    if normalize_url(draft.article_url) in load_posted(history):
        print("この記事は投稿済みです。何もしません。")
        return 0
    try:
        post_id = publish_image(
            _image_url(env, draft.date), draft.caption, env["INSTAGRAM_USER_ID"], env["INSTAGRAM_ACCESS_TOKEN"]
        )
    except InstagramError as exc:
        print(f"投稿に失敗しました: {exc}", file=sys.stderr)
        return 1
    record_posted(history, draft.article_url, datetime.now(JST).isoformat())
    print(f"投稿しました（投稿ID: {post_id}）")
    return 0


def cmd_refresh(args, env: dict, root: Path) -> int:
    try:
        new = refresh_token(env["INSTAGRAM_ACCESS_TOKEN"])
        store_secret("INSTAGRAM_ACCESS_TOKEN", new, env)
    except InstagramError as exc:
        print(f"トークンの更新に失敗しました: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError:
        print("新しいトークンの保存に失敗しました（GH_ADMIN_TOKEN の権限を確認してください）", file=sys.stderr)
        return 1
    print("トークンを更新しました。")
    return 0


def main(argv=None, env: dict | None = None, root: Path = Path(".")) -> int:
    parser = argparse.ArgumentParser(prog="aibot")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("draft")
    p.add_argument("--now", help="現在日時を固定する（ISO8601。テスト・練習用）")
    p.set_defaults(func=cmd_draft)
    p = sub.add_parser("publish")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    p.set_defaults(func=cmd_publish)
    p = sub.add_parser("refresh-token")
    p.set_defaults(func=cmd_refresh)
    args = parser.parse_args(argv)
    return args.func(args, dict(os.environ) if env is None else env, root)

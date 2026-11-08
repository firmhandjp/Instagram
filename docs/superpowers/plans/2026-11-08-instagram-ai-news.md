# Instagram AIニュース自動投稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 毎朝AIニュース1本を「1枚画像＋解説文」の下書きにし、GitHub の承認後に Instagram へ自動投稿する。

**Architecture:** Python パッケージ `aibot` を、GitHub Actions の2つのジョブ（下書き → 承認待ち → 投稿）から呼ぶ。部品は収集・文章・画像・投稿の4つに分け、それぞれ単体でテストできる。承認は Environment の Required reviewers で行い、外すと完全自動になる。

**Tech Stack:** Python 3.11+、feedparser、Pillow、anthropic、requests、tzdata、pytest、responses、GitHub Actions、`gh` CLI

**Spec:** `docs/superpowers/specs/2026-11-08-instagram-ai-news-design.md`

## Global Constraints

- 投稿は Instagram API with Instagram Login（`https://graph.instagram.com`、バージョン指定なし）を使う。Facebook ページは使わない。
- 画像は **JPEG のみ**、1080×1350。公開URLは `https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/drafts/{date}.jpg`。
- 日付はすべて JST（`Asia/Tokyo`）の `YYYY-MM-DD`。下書きは毎朝 7:00 JST（cron `0 22 * * *`）。
- 解説文は 2200 文字以内、ハッシュタグは 3〜10 個。出典（媒体名とURL）を必ず入れる。
- 画像の文字は Pillow で載せる（AI画像生成は使わない）。フォントは Noto Sans JP（OFL）を `fonts/` に同梱し、ライセンス文も置く。
- 鍵（`ANTHROPIC_API_KEY`、`INSTAGRAM_ACCESS_TOKEN`、`INSTAGRAM_USER_ID`、`GH_ADMIN_TOKEN`）は GitHub Secrets と環境変数だけに置く。リポジトリは公開なので、鍵の値をログや出力に出さない。
- Claude のモデル名は `config.toml` の `claude.model`（初期値 `claude-sonnet-5-5`）で変える。
- 作業ブランチは `feature/instagram-ai-news`。コミットメッセージの末尾に `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>` を付ける。スケジュール実行は main でのみ動くため、マージは Task 8 で行う。
- 利用者は IT 初心者。`docs/setup-guide.md` は日本語、番号付き手順、専門用語には短い説明を添える。

## Review Focus

1. 情報源の1つが壊れている・空・遅い → 他の情報源は処理を続ける（Task 2）。
2. Claude の返答が JSON でない、項目が欠けている、長すぎる、選んだ番号が範囲外 → 下書きを作らず失敗する。投稿はされない（Task 3）。
3. 見出しが極端に長い、または英数字・絵文字が混じる → 画像の余白に文字がはみ出さない（Task 4）。
4. 同じ記事がURLの追跡パラメータ違い（`?utm_source=`）で再登場、または同日に再実行 → 二重に投稿しない（Task 2、Task 6）。
5. Instagram 側でコンテナ作成・処理・公開のどこかが失敗 → 履歴に記録しない。新しいトークンやAPIキーはログに出ない（Task 5、Task 6）。

---

## File Structure

| ファイル | 責務 |
|---|---|
| `pyproject.toml` | 依存関係、pytest 設定 |
| `config.toml` | 情報源、取得期間、モデル名、画像サイズ |
| `src/aibot/models.py` | `Article`、`Draft` |
| `src/aibot/config.py` | 設定の読み込み |
| `src/aibot/history.py` | 投稿履歴の読み書き、URL の正規化 |
| `src/aibot/collect.py` | RSS 取得、新着の絞り込み |
| `src/aibot/write.py` | Claude による選定と文章づくり、検証 |
| `src/aibot/render.py` | 見出し画像の描画 |
| `src/aibot/instagram.py` | 投稿、トークン更新 |
| `src/aibot/cli.py`, `__main__.py` | `draft` / `publish` / `refresh-token` |
| `.github/workflows/daily.yml`, `refresh-token.yml` | 毎朝の流れ、トークン更新 |
| `docs/setup-guide.md` | 準備手順（利用者向け） |
| `data/posted.json`, `drafts/` | 投稿履歴、下書き（画像と JSON） |
| `tests/` | 各部品のテスト |

---

### Task 1: 土台と情報源の確定

**Files:**
- Create: `pyproject.toml`, `config.toml`, `data/posted.json`（中身は `[]`）, `src/aibot/__init__.py`, `src/aibot/models.py`, `src/aibot/config.py`, `src/aibot/history.py`, `tests/test_config.py`, `tests/test_history.py`

**Interfaces:**
- Produces:
  - `models.Article(title: str, url: str, source: str, summary: str, published: datetime)`（frozen dataclass、`published` はタイムゾーン付き）
  - `models.Draft(headline: str, caption: str, article_url: str, source: str, date: str)`（frozen dataclass）、`Draft.to_json() -> str`、`Draft.from_json(text: str) -> Draft`
  - `config.Config`（`feeds: list[Feed]`、`lookback_hours: int`、`max_candidates: int`、`model: str`、`image_width: int`、`image_height: int`）、`config.Feed(name: str, url: str)`、`config.load_config(path: Path) -> Config`
  - `history.normalize_url(url: str) -> str`、`history.load_posted(path: Path) -> set[str]`（正規化済みURLの集合）、`history.record_posted(path: Path, url: str, posted_at: str) -> None`

- [ ] **Step 1: ブランチを作る** — `git switch -c feature/instagram-ai-news`
- [ ] **Step 2: 情報源を確定する（ユーザーの承認が必要）** — 候補（AI関連の国内メディア、主要AI企業の公式ブログなど）の RSS が取得できるか `curl` で確認する。使えるものだけを媒体名・URL・取得できた件数の表にして、ユーザーに見せて承認を得る。承認までこの Task の以降は進めない。
- [ ] **Step 3: 失敗するテストを書く**
  - `test_load_config_reads_feeds`: 一時ファイルの TOML から `load_config` すると `feeds[0].name`、`lookback_hours == 24`、`model == "claude-sonnet-5-5"` を返す。
  - `test_normalize_url_drops_tracking`: `normalize_url("https://Example.com/a/?utm_source=x&id=1#top")` が `"https://example.com/a?id=1"` になる。
  - `test_normalize_url_equal_after_trailing_slash`: `"https://e.com/a/"` と `"https://e.com/a"` の正規化結果が等しい。
  - `test_record_and_load_posted`: `record_posted` 後に `load_posted` が正規化済みURLを含む。ファイルが無い場合は空集合を返す。
  - `test_draft_json_roundtrip`: `Draft.from_json(d.to_json()) == d`（日本語が `\u` 化されない）。
- [ ] **Step 4: 失敗を確認する** — Run: `pytest tests -v`　Expected: FAIL（モジュールが無い）
- [ ] **Step 5: 実装する** — 上記シグネチャで実装する。TOML は標準の `tomllib`、タイムゾーンは `zoneinfo`。`normalize_url` は `utm_*`・`fbclid`・`gclid` を除き、ホストを小文字にし、フラグメントと末尾スラッシュを除く。`config.toml` に Step 2 で承認された情報源を `[[news.feeds]]` で入れる。
- [ ] **Step 6: 成功を確認する** — Run: `pytest tests -v`　Expected: PASS
- [ ] **Step 7: コミットする** — `git add -A && git commit -m "feat: 設定・履歴・モデルの土台を追加"`

### Task 2: ニュース収集

**Files:**
- Create: `src/aibot/collect.py`, `tests/test_collect.py`, `tests/fixtures/sample.xml`（記事3件、うち1件は25時間前）

**Interfaces:**
- Consumes: `Article`、`Feed`、`normalize_url`
- Produces: `collect.fetch_articles(feeds: list[Feed], now: datetime, lookback_hours: int, fetch=feedparser.parse) -> list[Article]`（新しい順）、`collect.select_candidates(articles: list[Article], posted: set[str], limit: int) -> list[Article]`

- [ ] **Step 1: 失敗するテストを書く**
  - `test_fetch_filters_by_lookback`: fixture から 24 時間以内の2件だけ返る。
  - `test_fetch_isolates_broken_feed`: 1つ目の `fetch` が例外を投げても、2つ目の情報源の記事は返る。（Review Focus 1）
  - `test_fetch_handles_empty_feed`: エントリが0件でも `[]` を返し、例外を出さない。
  - `test_select_excludes_posted_with_tracking_params`: 履歴に `https://e.com/a` があれば、`https://e.com/a?utm_source=x` の記事は除かれる。（Review Focus 4）
  - `test_select_respects_limit`: 件数が `limit` を超えない。
- [ ] **Step 2: 失敗を確認する** — Run: `pytest tests/test_collect.py -v`　Expected: FAIL
- [ ] **Step 3: 実装する** — `published_parsed` が無いエントリは捨てる。1つの情報源の失敗は標準エラーに媒体名だけ出して続行する。`fetch` を引数にして、テストでネットワークを使わない。
- [ ] **Step 4: 成功を確認する** — Run: `pytest tests/test_collect.py -v`　Expected: PASS
- [ ] **Step 5: コミットする** — `git add -A && git commit -m "feat: ニュース収集を追加"`

### Task 3: 文章づくり（Claude）

**Files:**
- Create: `src/aibot/write.py`, `tests/test_write.py`

**Interfaces:**
- Consumes: `Article`、`Draft`
- Produces: `write.generate_draft(candidates: list[Article], client, model: str, date: str) -> Draft`、`write.DraftError(Exception)`、`write.build_caption(body: str, hashtags: list[str], source: str, url: str) -> str`

`client` は `anthropic.Anthropic` 互換で、`client.messages.create(...)` の結果の `content[0].text` を使う。Claude には JSON `{"index": int, "headline": str, "body": str, "hashtags": [str]}` だけを返させる。

- [ ] **Step 1: 失敗するテストを書く**（偽の client を使う。ネットワーク不使用）
  - `test_generate_draft_builds_caption_with_source`: 正常な返答で `Draft.caption` に媒体名とURLが入り、`article_url` が選ばれた記事のURLになる。
  - `test_caption_format`: `build_caption("本文", ["#AI", "#ニュース", "#生成AI"], "媒体A", "https://e.com/a")` の結果が「本文」「出典: 媒体A https://e.com/a」「ハッシュタグ」をこの順に空行区切りで含む。
  - `test_rejects_non_json`: JSON でない返答 → `DraftError`。
  - `test_rejects_missing_field`: `headline` が無い → `DraftError`。
  - `test_rejects_index_out_of_range`: `index` が範囲外（負数を含む）→ `DraftError`。
  - `test_rejects_too_long`: 見出し 41 文字、本文 601 文字、ハッシュタグ 2 個または 11 個、`#` で始まらないタグ、全体 2200 文字超 のそれぞれで `DraftError`。（Review Focus 2）
  - `test_prompt_forbids_adding_facts`: `client.messages.create` に渡された system に「記事にない数字や事実を足さない」「元の文章を写さず要約する」の趣旨の文が入る。
- [ ] **Step 2: 失敗を確認する** — Run: `pytest tests/test_write.py -v`　Expected: FAIL
- [ ] **Step 3: 実装する** — 候補は番号・媒体名・題名・概要を並べて渡す。JSON は前後に余計な文字があっても最初の `{` から最後の `}` までを取り出して読む。検証はコード側で行い（見出し 40 文字以内、本文 600 文字以内、タグ 3〜10 個で各 `#` 始まり、全体 2200 文字以内）、1つでも外れたら `DraftError`。出典は `build_caption` がコードで必ず付ける。
- [ ] **Step 4: 成功を確認する** — Run: `pytest tests/test_write.py -v`　Expected: PASS
- [ ] **Step 5: コミットする** — `git add -A && git commit -m "feat: Claudeによる文章づくりを追加"`

### Task 4: 画像づくり

**Files:**
- Create: `src/aibot/render.py`, `tests/test_render.py`, `fonts/NotoSansJP-Bold.ttf`, `fonts/OFL.txt`

**Interfaces:**
- Produces: `render.render_image(headline: str, source: str, out_path: Path, font_path: Path, width: int = 1080, height: int = 1350) -> None`（JPEG で保存）

- [ ] **Step 1: フォントを置く** — Noto Sans JP の Bold とライセンス文（OFL）を公式の配布元から取得して `fonts/` に置く。取得元のURLをコミットメッセージに書く。
- [ ] **Step 2: 失敗するテストを書く**
  - `test_output_is_jpeg_with_expected_size`: 保存したファイルを開くと `format == "JPEG"` かつ `size == (1080, 1350)`。
  - `test_long_headline_stays_inside_margins`: 40 文字の日本語見出し、および 200 文字の見出しでも例外が出ず、左右 60px・上下 60px の余白の帯が背景色だけ。（Review Focus 3）
  - `test_mixed_text_renders`: `"GPT-5 が登場 🚀 Claude 5"` でも例外が出ない（絵文字は描けなくてもよいが、落ちない）。
  - `test_different_headlines_make_different_images`: 見出しが違えば画像のバイト列が違う。
- [ ] **Step 3: 失敗を確認する** — Run: `pytest tests/test_render.py -v`　Expected: FAIL
- [ ] **Step 4: 実装する** — 背景は単色、上部に媒体名、中央に見出し。フォントサイズを 88 から 48 まで下げながら、最大6行・余白内に収まる最大サイズを探す。それでも収まらなければ末尾を「…」で切る。文字幅の計算は Pillow の `textlength` で行い、折り返しは1文字ずつ幅を見て行う。JPEG 品質は 92。
- [ ] **Step 5: 成功を確認する** — Run: `pytest tests/test_render.py -v`　Expected: PASS。出来た画像を1枚、目で見て確認する。
- [ ] **Step 6: コミットする** — `git add -A && git commit -m "feat: 見出し画像の描画を追加"`

### Task 5: Instagram 投稿とトークン更新

**Files:**
- Create: `src/aibot/instagram.py`, `tests/test_instagram.py`

**Interfaces:**
- Produces:
  - `instagram.publish_image(image_url: str, caption: str, user_id: str, token: str, sleep=time.sleep) -> str`（投稿IDを返す）
  - `instagram.refresh_token(token: str) -> str`（新しいトークンを返す）
  - `instagram.InstagramError(Exception)`

流れ: `POST /{user_id}/media`（`image_url`、`caption`）→ コンテナID → `GET /{container_id}?fields=status_code` を `FINISHED` になるまで最大10回、3秒間隔で確認 → `POST /{user_id}/media_publish`（`creation_id`）。更新は `GET /refresh_access_token?grant_type=ig_refresh_token`。

- [ ] **Step 1: 失敗するテストを書く**（`responses` で HTTP を偽装）
  - `test_publish_happy_path`: 3つの呼び出しが順に行われ、投稿IDが返る。`access_token` と `caption` が正しく送られる。
  - `test_publish_waits_until_finished`: 状態が `IN_PROGRESS` → `FINISHED` の順なら、公開は `FINISHED` の後に1回だけ行われる。
  - `test_publish_raises_on_container_error`: コンテナ作成が 400 → `InstagramError`、公開は呼ばれない。（Review Focus 5）
  - `test_publish_raises_on_status_error`: 状態が `ERROR` → `InstagramError`、公開は呼ばれない。
  - `test_publish_raises_on_timeout`: 10回確認しても `IN_PROGRESS` → `InstagramError`。
  - `test_error_message_hides_token`: 失敗時の例外メッセージにトークンの値が含まれない。
  - `test_refresh_token_returns_new_token`: 新しい `access_token` を返し、レスポンスに無い場合は `InstagramError`。
- [ ] **Step 2: 失敗を確認する** — Run: `pytest tests/test_instagram.py -v`　Expected: FAIL
- [ ] **Step 3: 実装する** — `requests` を使い、タイムアウトは30秒。エラー時はステータスコードと API が返したエラーメッセージだけを例外にし、リクエストURL（トークンを含む）は入れない。
- [ ] **Step 4: 成功を確認する** — Run: `pytest tests/test_instagram.py -v`　Expected: PASS
- [ ] **Step 5: コミットする** — `git add -A && git commit -m "feat: Instagram投稿とトークン更新を追加"`

### Task 6: コマンドの組み立て

**Files:**
- Create: `src/aibot/cli.py`, `src/aibot/__main__.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: Task 1〜5 のすべて
- Produces:
  - `python -m aibot draft [--now ISO8601]`: 下書きを `drafts/{date}.json` と `drafts/{date}.jpg` に保存する。`$GITHUB_OUTPUT` があれば `date={date}` を書き、`$GITHUB_STEP_SUMMARY` があれば画像（公開URL）と解説文と出典を Markdown で書く。候補が0件なら終了コード 1。
  - `python -m aibot publish --date YYYY-MM-DD`: 下書きを読み、投稿し、成功後に履歴へ記録する。
  - `python -m aibot refresh-token`: トークンを更新し、`gh secret set INSTAGRAM_ACCESS_TOKEN` で保存する。
  - `cli.store_secret(name: str, value: str) -> None`（`gh secret set {name}` を標準入力で呼ぶ。値は引数にも出力にも出さない）
  - 環境変数: `ANTHROPIC_API_KEY`、`INSTAGRAM_ACCESS_TOKEN`、`INSTAGRAM_USER_ID`、`GITHUB_REPOSITORY`、`GH_ADMIN_TOKEN`（`gh` には `GH_TOKEN` として渡す）

- [ ] **Step 1: 失敗するテストを書く**（Task 2〜5 の関数は差し替える）
  - `test_draft_writes_files_and_outputs_date`: 下書きJSONと画像ができ、`$GITHUB_OUTPUT` に `date=2026-11-09` が書かれる（`--now` で日時を固定）。
  - `test_draft_fails_when_no_candidates`: 候補が0件 → 終了コード 1、ファイルは作られない。
  - `test_draft_fails_when_draft_error`: `DraftError` → 終了コード 1、ファイルは作られない。
  - `test_publish_records_history_after_success`: 成功後に履歴へ記録される。投稿に渡す `image_url` が `https://raw.githubusercontent.com/o/r/main/drafts/2026-11-09.jpg`。
  - `test_publish_does_not_record_on_failure`: `InstagramError` → 終了コード 1、履歴は変わらない。（Review Focus 5）
  - `test_publish_skips_already_posted_article`: 履歴にある記事の下書きなら、投稿を呼ばずに終了コード 0 で終わる。（Review Focus 4）
  - `test_refresh_token_never_prints_token`: 新トークンの値が標準出力・標準エラーに出ず、`store_secret` に渡される。
- [ ] **Step 2: 失敗を確認する** — Run: `pytest tests/test_cli.py -v`　Expected: FAIL
- [ ] **Step 3: 実装する** — `argparse` のサブコマンドにする。下書きの日付は JST。
- [ ] **Step 4: 全テストの成功を確認する** — Run: `pytest -v`　Expected: すべて PASS
- [ ] **Step 5: 練習モードを手元で試す** — ユーザーが `ANTHROPIC_API_KEY` を用意したら `python -m aibot draft` を実行し、`drafts/` の画像と文章を一緒に確認する。（鍵が無ければ、準備が済むまで保留して Task 7 へ進む）
- [ ] **Step 6: コミットする** — `git add -A && git commit -m "feat: draft/publish/refresh-token コマンドを追加"`

### Task 7: 自動実行の設定と準備ガイド

**Files:**
- Create: `.github/workflows/daily.yml`, `.github/workflows/refresh-token.yml`, `docs/setup-guide.md`

**Interfaces:**
- Consumes: `python -m aibot draft` / `publish` / `refresh-token`
- Produces: ワークフロー `daily`（`schedule` と `workflow_dispatch`。入力 `dry_run`）、`refresh-token`（毎月1日と15日の 00:00 UTC）

- [ ] **Step 1: `daily.yml` を作る**
  - ジョブ `draft`: 権限 `contents: write`。チェックアウト → Python 3.11 → 依存インストール → `python -m aibot draft` → `drafts/` と `data/` を `git add` して、変更があれば `git pull --rebase` のあと main へ push。出力 `date` をジョブ出力にする。
  - ジョブ `publish`: `needs: draft`、`if: github.event.inputs.dry_run != 'true'`、`environment: instagram-publish`、権限 `contents: write`。`ref: main` でチェックアウトし直す（下書きの画像が入っているため）→ `python -m aibot publish --date ${{ needs.draft.outputs.date }}` → 履歴を push。
  - 両ジョブに `timeout-minutes: 15`、`concurrency: instagram-daily`（同時実行しない）を付ける。鍵は `secrets.*` から環境変数で渡す。
- [ ] **Step 2: `refresh-token.yml` を作る** — `python -m aibot refresh-token` を実行する。`GH_ADMIN_TOKEN` と `INSTAGRAM_ACCESS_TOKEN` を `secrets.*` から渡す。
- [ ] **Step 3: YAML の文法を確認する** — Run: `python -c "import yaml,sys;[yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/daily.yml .github/workflows/refresh-token.yml`　Expected: エラーなし
- [ ] **Step 4: `docs/setup-guide.md` を書く** — 次の見出しの順に、画面の操作を番号付きで書く。各手順の最後に「うまくいったかの目印」を1行添える。
  1. Instagram をプロアカウントに切り替える
  2. Meta の開発者サイトでアプリを登録し、Instagram のログインを設定して、`instagram_business_basic` と `instagram_business_content_publish` の権限で、長期トークンと Instagram ユーザーIDを取得する
  3. Claude の API キーを取得する
  4. GitHub で公開リポジトリを作り、Secrets（`ANTHROPIC_API_KEY`、`INSTAGRAM_ACCESS_TOKEN`、`INSTAGRAM_USER_ID`、`GH_ADMIN_TOKEN`）を登録する。`GH_ADMIN_TOKEN` は、このリポジトリだけを対象にし、Secrets の書き込み権限のみを持つ個人用アクセストークンにする
  5. Environment `instagram-publish` を作り、Required reviewers に自分を入れる
  6. 完全自動に切り替えたいとき（Required reviewers を外す）と、止めたいとき（ワークフローを無効にする）
- [ ] **Step 5: コミットする** — `git add -A && git commit -m "feat: 自動実行の設定と準備ガイドを追加"`

### Task 8: 本番での確認とマージ

**Files:** なし（運用の確認）

- [ ] **Step 1: ユーザーが準備を終える** — `docs/setup-guide.md` を一緒に進める。Meta の画面の確認は、ユーザーの画面を見ながら行う。
- [ ] **Step 2: ブランチを main にマージして push する** — ユーザーに確認してから行う。
- [ ] **Step 3: 練習モードを実行する** — Actions の `daily` を `dry_run=true` で手動実行する。Expected: `draft` ジョブだけが成功し、実行画面の概要に画像と解説文が表示される。内容をユーザーが確認する。
- [ ] **Step 4: 本番で1回だけ投稿する** — `dry_run=false` で手動実行し、承認ボタンを押す。Expected: Instagram に投稿され、`data/posted.json` に記録が追加される。Instagram が `raw.githubusercontent.com` の画像を取得できなかった場合は、そこで画像の置き場所の方針をユーザーと相談する。
- [ ] **Step 5: 同日の再実行で二重投稿されないことを確認する** — もう一度手動実行（`dry_run=true`）し、下書きが前回投稿した記事とは別の記事になることを確認する。
- [ ] **Step 6: トークン更新を手動実行する** — `refresh-token` を手動実行する。Expected: 成功し、ログに新しいトークンの値が出ていない。
- [ ] **Step 7: 数日間は承認制で運用する** — 完全自動への切り替えは、ユーザーが品質を見て決める。

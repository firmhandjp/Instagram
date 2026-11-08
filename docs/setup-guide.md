# 準備ガイド（Instagram AIニュース自動投稿）

最初の1回だけ行う準備です。所要時間の目安は 60〜90 分です。
画面の名前や位置は、Instagram・Meta・GitHub の更新で変わることがあります。違っていたら、近い名前の項目を探してください。

> 用語の説明
> - **プロアカウント**：Instagram の「ビジネス」または「クリエイター」アカウント。自動投稿に必要です。
> - **トークン**：Instagram に「このプログラムに投稿を任せる」と伝えるための合言葉のようなものです。約60日で切れます。
> - **API キー**：Claude（AI）をプログラムから使うための合言葉です。
> - **Secrets**：GitHub の「鍵の金庫」。合言葉をここに入れると、他の人には見えません。

---

## 1. Instagram をプロアカウントに切り替える（無料・数分）

1. Instagram アプリで自分のプロフィールを開く。
2. 右上のメニュー（三）→「設定とアクティビティ」を開く。
3. 「アカウントの種類とツール」→「プロアカウントに切り替える」を選ぶ。
4. 「ビジネス」または「クリエイター」を選び、案内に従って進める。

目印：プロフィール画面に「プロフェッショナルダッシュボード」が表示される。

> 社外発信用なので、個人用とは別に、会社用のアカウントを新しく作ってプロアカウントにする方法もおすすめします。

## 2. Meta の開発者サイトでアプリを登録し、トークンを取得する

1. https://developers.facebook.com/ を開き、Facebook アカウントでログインして、開発者として登録する。
2. 「アプリを作成」を押す。用途は「その他」→ アプリタイプは「ビジネス」を選ぶ。アプリ名は自由（例：会社名 AIニュース）。
3. アプリのダッシュボードで「Instagram」の製品を追加する。
4. 「Instagram API の設定（Instagram ログインによる API 設定）」を開く。
5. 「Instagram アカウントを追加」から、手順 1 のアカウントを追加し、ログインして許可する。
6. 許可する権限に、次の2つが含まれていることを確認する。
   - `instagram_business_basic`
   - `instagram_business_content_publish`
7. 追加したアカウントの横にある「アクセストークンを生成」を押し、表示されたトークンを**安全な場所に一時的にメモ**する（人に見せない）。
8. 同じ画面に表示される **Instagram ユーザーID**（数字）もメモする。

目印：トークン（長い文字列）と、ユーザーID（数字）が手元にある。

> この手順は画面の確認が必要な部分です。うまく進まないときは、画面を見せてください。一緒に確認します。

## 3. Claude の API キーを取得する

1. https://console.anthropic.com/ にログインする。
2. 「API Keys」→「Create Key」を押す。名前は自由（例：instagram-news）。
3. 表示されたキーを**安全な場所に一時的にメモ**する（この画面を閉じると二度と表示されません）。
4. 利用料のため、支払い方法の登録と、少額（例：数ドル）のチャージを行う。

目印：`sk-ant-` で始まるキーが手元にある。

## 4. GitHub でリポジトリを作り、Secrets を登録する

1. https://github.com/ でアカウントを作る（既にあれば不要）。
2. 右上の「＋」→「New repository」を押す。名前は自由。**Public（公開）**を選んで作成する。
3. このプロジェクトのファイルを、作成したリポジトリにアップロードする（私が手順をご案内します）。
4. 個人用アクセストークンを作る（トークンの自動更新に使います）。
   1. 右上のアイコン → Settings → 一番下の「Developer settings」→「Personal access tokens」→「Fine-grained tokens」→「Generate new token」。
   2. 名前は自由、期限は最長にする。
   3. 「Only select repositories」で、作成したリポジトリだけを選ぶ。
   4. 「Repository permissions」の「Secrets」を **Read and write** にする。他は変えない。
   5. 作成して、表示されたトークンをメモする。
5. リポジトリの Settings → 「Secrets and variables」→「Actions」→「New repository secret」で、次の4つを1つずつ登録する。

| 名前 | 入れるもの |
|---|---|
| `ANTHROPIC_API_KEY` | 手順 3 のキー |
| `INSTAGRAM_ACCESS_TOKEN` | 手順 2 のトークン |
| `INSTAGRAM_USER_ID` | 手順 2 のユーザーID |
| `GH_ADMIN_TOKEN` | 手順 4 の個人用アクセストークン |

目印：Secrets の一覧に4つの名前が並ぶ（値は表示されません）。
登録が終わったら、手元のメモは削除してください。

## 5. 承認ボタンを設定する

1. リポジトリの Settings → 「Environments」→「New environment」を押す。
2. 名前を `instagram-publish` にして作成する。
3. 「Required reviewers」にチェックを入れ、自分のアカウントを選んで「Save protection rules」を押す。

目印：Environment の画面に、自分の名前が Reviewers として表示される。

## 6. 切り替えと停止の方法

- **完全自動にしたいとき**：Environments → `instagram-publish` を開き、「Required reviewers」のチェックを外して保存する。以後は承認なしで、毎朝そのまま投稿されます。
- **一時的に止めたいとき**：リポジトリの Actions → 左の「daily」→ 右上「…」→「Disable workflow」を押す。再開は「Enable workflow」。
- **投稿を取り消したいとき**：Instagram アプリで、その投稿を削除する。

## 7. 毎日の確認（承認制のあいだ）

1. 毎朝 7 時ごろ、GitHub に「承認待ち」が表示されます（メールでも通知が届きます）。
2. 「Actions」→ 最新の「daily」を開き、「今日の下書き」で画像と解説文を確認する。
3. 問題なければ「Review deployments」→ `instagram-publish` にチェック →「Approve and deploy」を押す。
4. 問題があれば「Reject」を押す。その日は投稿されません。

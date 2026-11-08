from __future__ import annotations

import time

import requests

GRAPH = "https://graph.instagram.com"
TIMEOUT = 30
POLL_TIMES = 10
POLL_INTERVAL = 3


class InstagramError(Exception):
    """Instagram API の呼び出しに失敗した。メッセージにトークンは含めない。"""


def _error_text(resp: requests.Response) -> str:
    try:
        msg = resp.json().get("error", {}).get("message")
    except ValueError:
        msg = None
    return f"HTTP {resp.status_code}: {msg}" if msg else f"HTTP {resp.status_code}"


def _call(method: str, path: str, **kwargs) -> dict:
    try:
        resp = requests.request(method, f"{GRAPH}/{path}", timeout=TIMEOUT, **kwargs)
    except requests.RequestException as exc:  # 例外文に URL（トークン）が入りうるので型名だけ出す
        raise InstagramError(f"通信に失敗しました ({type(exc).__name__})") from None
    if not resp.ok:
        raise InstagramError(_error_text(resp))
    try:
        return resp.json()
    except ValueError:
        raise InstagramError("応答を読めませんでした") from None


def publish_image(image_url: str, caption: str, user_id: str, token: str, sleep=time.sleep) -> str:
    """画像を投稿し、投稿IDを返す。コンテナ作成 → 処理完了待ち → 公開。"""
    container = _call(
        "POST", f"{user_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
    ).get("id")
    if not container:
        raise InstagramError("コンテナIDが返りませんでした")

    for _ in range(POLL_TIMES):
        status = _call(
            "GET", container, params={"fields": "status_code", "access_token": token}
        ).get("status_code")
        if status == "FINISHED":
            break
        if status in ("ERROR", "EXPIRED"):
            raise InstagramError(f"画像の処理に失敗しました ({status})")
        sleep(POLL_INTERVAL)
    else:
        raise InstagramError("画像の処理が時間内に終わりませんでした")

    post_id = _call(
        "POST", f"{user_id}/media_publish",
        data={"creation_id": container, "access_token": token},
    ).get("id")
    if not post_id:
        raise InstagramError("投稿IDが返りませんでした")
    return post_id


def refresh_token(token: str) -> str:
    data = _call(
        "GET", "refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": token},
    )
    new = data.get("access_token")
    if not new:
        raise InstagramError("新しいトークンが返りませんでした")
    return new

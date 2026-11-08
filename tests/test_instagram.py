import pytest
import responses

from aibot.instagram import InstagramError, publish_image, refresh_token

BASE = "https://graph.instagram.com"
TOKEN = "SECRET-TOKEN-123"


def _publish(**kw):
    return publish_image("https://img.example/a.jpg", "解説文", "42", TOKEN, sleep=lambda s: None, **kw)


@responses.activate
def test_publish_happy_path():
    responses.post(f"{BASE}/42/media", json={"id": "c1"})
    responses.get(f"{BASE}/c1", json={"status_code": "FINISHED"})
    responses.post(f"{BASE}/42/media_publish", json={"id": "p1"})
    assert _publish() == "p1"
    first = responses.calls[0].request
    body = first.body if isinstance(first.body, str) else first.body.decode()
    assert "image_url=" in body and TOKEN in body
    assert "%E8%A7%A3%E8%AA%AC%E6%96%87" in body  # caption（解説文）
    assert responses.calls[-1].request.url.endswith("/42/media_publish")


@responses.activate
def test_publish_waits_until_finished():
    responses.post(f"{BASE}/42/media", json={"id": "c1"})
    responses.get(f"{BASE}/c1", json={"status_code": "IN_PROGRESS"})
    responses.get(f"{BASE}/c1", json={"status_code": "FINISHED"})
    responses.post(f"{BASE}/42/media_publish", json={"id": "p1"})
    assert _publish() == "p1"
    urls = [c.request.url for c in responses.calls]
    assert sum(u.endswith("/media_publish") for u in urls) == 1
    assert urls[-1].endswith("/media_publish")


@responses.activate
def test_publish_raises_on_container_error():
    responses.post(f"{BASE}/42/media", status=400, json={"error": {"message": "bad image"}})
    with pytest.raises(InstagramError, match="bad image"):
        _publish()
    assert len(responses.calls) == 1  # 公開は呼ばれない


@responses.activate
def test_publish_raises_on_status_error():
    responses.post(f"{BASE}/42/media", json={"id": "c1"})
    responses.get(f"{BASE}/c1", json={"status_code": "ERROR"})
    with pytest.raises(InstagramError):
        _publish()
    assert not any(c.request.url.endswith("/media_publish") for c in responses.calls)


@responses.activate
def test_publish_raises_on_timeout():
    responses.post(f"{BASE}/42/media", json={"id": "c1"})
    responses.get(f"{BASE}/c1", json={"status_code": "IN_PROGRESS"})
    with pytest.raises(InstagramError):
        _publish()
    assert not any(c.request.url.endswith("/media_publish") for c in responses.calls)


@responses.activate
def test_error_message_hides_token():
    responses.post(f"{BASE}/42/media", status=500, body="oops")
    with pytest.raises(InstagramError) as ei:
        _publish()
    assert TOKEN not in str(ei.value)


@responses.activate
def test_refresh_token_returns_new_token():
    responses.get(f"{BASE}/refresh_access_token", json={"access_token": "NEW", "expires_in": 5183944})
    assert refresh_token("OLD") == "NEW"
    assert "grant_type=ig_refresh_token" in responses.calls[0].request.url


@responses.activate
def test_refresh_token_missing_in_response():
    responses.get(f"{BASE}/refresh_access_token", json={"expires_in": 1})
    with pytest.raises(InstagramError):
        refresh_token("OLD")


@responses.activate
def test_wait_for_image_retries_until_available():
    from aibot.instagram import wait_for_image

    url = "https://raw.example/a.jpg"
    responses.head(url, status=404)
    responses.head(url, status=200)
    wait_for_image(url, sleep=lambda s: None)
    assert len(responses.calls) == 2


@responses.activate
def test_wait_for_image_gives_up():
    from aibot.instagram import wait_for_image

    url = "https://raw.example/a.jpg"
    responses.head(url, status=404)
    with pytest.raises(InstagramError):
        wait_for_image(url, sleep=lambda s: None)

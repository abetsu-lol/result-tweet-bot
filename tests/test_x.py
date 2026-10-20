import pytest

from bot.config import XAccount
from bot.http import HttpError
from bot.x import XClient, XPermissionError

APP = {"consumer_key": "ck", "consumer_secret": "cs"}
ACCOUNT = XAccount("at", "ats", "1")


class Response:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code, self._payload, self.headers, self.text = status, payload or {}, headers or {}, ""

    def json(self):
        return self._payload


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}
        self.auth = None

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_upload_then_reply_with_media():
    session = Session(Response(payload={"data": {"id": "m1"}}, headers={"x-access-level": "read-write"}),
                      Response(), Response(), Response(201, {"data": {"id": "p1"}}))
    client = XClient(APP, ACCOUNT, session)
    assert client.upload_png(b"png") == "m1"
    assert client.post("text", reply_to="root", media_ids=["m1"]) == "p1"
    urls = [url.replace("https://api.x.com", "") for _, url, _ in session.calls]
    assert urls == ["/2/media/upload/initialize", "/2/media/upload/m1/append", "/2/media/upload/m1/finalize", "/2/tweets"]
    assert session.calls[0][2]["json"]["total_bytes"] == 3
    assert session.calls[1][2]["files"]["media"][1] == b"png"
    assert session.calls[3][2]["json"] == {"text": "text", "reply": {"in_reply_to_tweet_id": "root"},
                                          "media": {"media_ids": ["m1"]}}


def test_read_only_token_stops_before_posting():
    session = Session(Response(payload={"data": {"id": "m1"}}, headers={"x-access-level": "read"}))
    with pytest.raises(XPermissionError):
        XClient(APP, ACCOUNT, session).upload_png(b"png")
    assert len(session.calls) == 1


def test_text_only_post_has_no_media_and_is_never_retried():
    session = Session(Response(503))
    with pytest.raises(HttpError):
        XClient(APP, ACCOUNT, session).post("t", reply_to="r")
    assert len(session.calls) == 1  # a retried post could be charged twice
    assert "media" not in session.calls[0][2]["json"]


def test_requests_are_signed_with_oauth1(monkeypatch):
    import requests
    captured = {}

    def fake_send(self, prepared, **kwargs):
        auth = prepared.headers["Authorization"]
        captured["auth"] = auth.decode() if isinstance(auth, bytes) else auth  # oauthlib 4 returns bytes
        response = requests.Response()
        response.status_code, response._content = 201, b'{"data": {"id": "p1"}}'
        return response
    monkeypatch.setattr(requests.Session, "send", fake_send)
    XClient(APP, ACCOUNT).post("t", reply_to="r")
    assert captured["auth"].startswith("OAuth ")
    assert 'oauth_consumer_key="ck"' in captured["auth"] and 'oauth_token="at"' in captured["auth"]
    assert "oauth_signature=" in captured["auth"] and "cs" not in captured["auth"].split("oauth_signature=")[0]

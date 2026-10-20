import pytest

from bot import http


class Response:
    def __init__(self, status, headers=None, text=""):
        self.status_code, self.headers, self.text = status, headers or {}, text


class Session:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = 0

    def request(self, method, url, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def test_retries_429_using_retry_after():
    waits = []
    session = Session(Response(429, {"Retry-After": "3"}), Response(200))
    assert http.request(session, "GET", "https://x/y", sleep=waits.append).status_code == 200
    assert waits == [3.0]


def test_retries_5xx_with_backoff_then_raises_without_query_string():
    waits = []
    session = Session(*[Response(503, text="down")] * 4)
    with pytest.raises(http.HttpError) as error:
        http.request(session, "GET", "https://x/y?api_key=secret", retries=3, sleep=waits.append)
    assert session.calls == 4 and waits == [1, 2, 4]
    assert "secret" not in str(error.value) and error.value.status == 503


def test_client_errors_are_not_retried():
    session = Session(Response(404))
    with pytest.raises(http.HttpError):
        http.request(session, "GET", "https://x/y", sleep=lambda _: None)
    assert session.calls == 1


def test_new_session_sets_user_agent():
    assert http.new_session().headers["User-Agent"].startswith("result-tweet-bot/")


def test_non_numeric_retry_after_falls_back_to_backoff_and_waits_are_capped():
    waits = []
    session = Session(Response(429, {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
                      Response(429, {"Retry-After": "600"}), Response(200))
    http.request(session, "GET", "https://x/y", max_wait=60, sleep=waits.append)
    assert waits == [1, 60]

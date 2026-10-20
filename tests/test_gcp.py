import base64
import gzip
import json

import pytest

from bot import gcp
from bot.http import HttpError


class Response:
    def __init__(self, status=200, text="", payload=None):
        self.status_code, self.text, self._payload, self.headers = status, text, payload, {}

    def json(self):
        return self._payload if self._payload is not None else json.loads(self.text)


class Session:
    """Records calls; responses are taken in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}

    def _next(self, method, url, kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)

    def get(self, url, **kwargs):
        return self._next("GET", url, kwargs)

    def post(self, url, **kwargs):
        return self._next("POST", url, kwargs)

    def request(self, method, url, **kwargs):
        return self._next(method, url, kwargs)


def test_secret_latest_decodes_payload():
    encoded = base64.b64encode("値 RGAPI-x".encode()).decode()
    session = Session(Response(payload={"payload": {"data": encoded}}))
    assert gcp.SecretStore(session).latest("projects/p/secrets/s") == "値 RGAPI-x"
    assert session.calls[0][1] == "https://secretmanager.googleapis.com/v1/projects/p/secrets/s/versions/latest:access"


def test_missing_objects_read_as_empty():
    bucket = gcp.Bucket(Session(Response(404), Response(404)), "b")
    assert bucket.read_json("state/main.json") is None
    assert bucket.read_ndjson("metrics/main/2026-10-19.ndjson") == []


def test_reads_parse_json_and_ndjson_and_escape_paths():
    session = Session(Response(text='{"a": 1}'), Response(text='{"x": 1}\n\n{"x": 2}\n'))
    bucket = gcp.Bucket(session, "b")
    assert bucket.read_json("state/main.json") == {"a": 1}
    assert bucket.read_ndjson("m.ndjson") == [{"x": 1}, {"x": 2}]
    assert session.calls[0][1].endswith("/b/b/o/state%2Fmain.json")


def test_read_errors_raise():
    with pytest.raises(HttpError) as error:
        gcp.Bucket(Session(Response(403, text="denied")), "b").read_json("state/main.json")
    assert error.value.status == 403


def test_write_once_uses_generation_precondition_and_reports_existing():
    session = Session(Response(200), Response(412))
    bucket = gcp.Bucket(session, "b")
    assert bucket.write_gzip_json_once("raw/matches/JP1_1.json.gz", {"m": 1}) is True
    assert bucket.write_gzip_json_once("raw/matches/JP1_1.json.gz", {"m": 1}) is False
    params = session.calls[0][2]["params"]
    assert params == {"uploadType": "media", "name": "raw/matches/JP1_1.json.gz", "ifGenerationMatch": "0"}
    assert json.loads(gzip.decompress(session.calls[0][2]["data"])) == {"m": 1}


def test_gzip_bytes_are_reproducible():
    session = Session(Response(200), Response(200))
    bucket = gcp.Bucket(session, "b")
    bucket.write_gzip_json_once("a", {"k": "値"})
    bucket.write_gzip_json_once("b", {"k": "値"})
    assert session.calls[0][2]["data"] == session.calls[1][2]["data"]


def test_plain_writes_overwrite_and_serialize():
    session = Session(Response(200), Response(200))
    bucket = gcp.Bucket(session, "b")
    bucket.write_json("state/main.json", {"名前": 1})
    bucket.write_ndjson("m.ndjson", [{"x": 1}, {"x": 2}])
    assert "ifGenerationMatch" not in session.calls[0][2]["params"]
    assert json.loads(session.calls[0][2]["data"].decode()) == {"名前": 1}
    assert session.calls[1][2]["data"].decode() == '{"x": 1}\n{"x": 2}\n'


def test_write_errors_raise_even_when_only_if_absent():
    with pytest.raises(HttpError):
        gcp.Bucket(Session(Response(500, text="err")), "b").write_gzip_json_once("a", {})
    with pytest.raises(HttpError):
        gcp.Bucket(Session(Response(403)), "b").write_json("a", {})

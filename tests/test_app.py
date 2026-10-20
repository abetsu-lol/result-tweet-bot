import json
from datetime import datetime

import pytest

from bot import app, collect, period
from test_config import ENV, account


class Secrets:
    def __init__(self, values):
        self.values = values

    def latest(self, name):
        return self.values[name]


@pytest.fixture
def wired(monkeypatch):
    """Runs app.run with fake secrets/bucket and a stubbed collector; returns the collected account ids."""
    accounts = [account(id="first"), account(id="second")]
    monkeypatch.setattr(app.gcp, "SecretStore", lambda session: Secrets({
        ENV["SECRET_ACCOUNTS"]: json.dumps(accounts), ENV["SECRET_RIOT_API_KEY"]: "RGAPI-test"}))
    monkeypatch.setattr(app.gcp, "Bucket", lambda session, name: object())
    seen = []
    return seen


def test_one_failing_account_does_not_stop_the_others(wired, monkeypatch, capsys):
    def fake_collect(acc, riot, bucket, now):
        wired.append(acc.id)
        if acc.id == "first":
            raise ValueError("boom")
        return collect.CollectResult(acc.id, "s", "e")
    monkeypatch.setattr(app.collect, "collect", fake_collect)

    with pytest.raises(RuntimeError, match="first"):
        app.run(datetime(2026, 10, 20, 12, 5, tzinfo=period.JST), env=ENV, session=object(), riot=object())

    assert wired == ["first", "second"]
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {"severity": "ERROR", "account_id": "first"}.items() <= next(l for l in logs if l["severity"] == "ERROR").items()
    assert "at-secret" not in json.dumps(logs)  # tokens never logged


def test_successful_run_returns_ok(wired, monkeypatch):
    monkeypatch.setattr(app.collect, "collect", lambda acc, *a: collect.CollectResult(acc.id, "s", "e"))
    assert app.run(env=ENV, session=object(), riot=object()) == "ok"


def test_unreadable_secrets_fail_the_whole_run(monkeypatch):
    class Broken:
        def latest(self, name):
            raise RuntimeError("permission denied")
    monkeypatch.setattr(app.gcp, "SecretStore", lambda session: Broken())
    monkeypatch.setattr(app.gcp, "Bucket", lambda session, name: object())
    with pytest.raises(RuntimeError, match="permission denied"):
        app.run(env=ENV, session=object(), riot=object())

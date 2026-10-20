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
    monkeypatch.setattr(app.publish, "publish", lambda acc, *a: (seen.append(("publish", acc.id)),
                                                                 app.publish.PublishResult(acc.id, "no_games"))[1])
    return seen


def test_one_failing_account_does_not_stop_the_others(wired, monkeypatch, capsys):
    def fake_collect(acc, riot, bucket, now):
        wired.append(acc.id)
        if acc.id == "first":
            raise ValueError("boom")
        return collect.CollectResult(acc.id, "s", "e")
    monkeypatch.setattr(app.collect, "collect", fake_collect)

    with pytest.raises(RuntimeError, match="first"):
        app.run(datetime(2026, 10, 20, 12, 5, tzinfo=period.JST), env=ENV, session=object(), riot=object(),
                champions=object())

    assert wired == ["first", "second", ("publish", "second")]  # no publishing after a failed collection
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert {"severity": "ERROR", "account_id": "first"}.items() <= next(l for l in logs if l["severity"] == "ERROR").items()
    assert "at-secret" not in json.dumps(logs)  # tokens never logged


def test_successful_run_returns_ok(wired, monkeypatch):
    monkeypatch.setattr(app.collect, "collect", lambda acc, *a: collect.CollectResult(acc.id, "s", "e"))
    assert app.run(env=ENV, session=object(), riot=object(), champions=object()) == "ok"


def test_unreadable_secrets_fail_the_whole_run(monkeypatch):
    class Broken:
        def latest(self, name):
            raise RuntimeError("permission denied")
    monkeypatch.setattr(app.gcp, "SecretStore", lambda session: Broken())
    monkeypatch.setattr(app.gcp, "Bucket", lambda session, name: object())
    with pytest.raises(RuntimeError, match="permission denied"):
        app.run(env=ENV, session=object(), riot=object(), champions=object())


def test_publishing_failure_is_reported_per_account(wired, monkeypatch, capsys):
    monkeypatch.setattr(app.collect, "collect", lambda acc, *a: collect.CollectResult(acc.id, "s", "e"))

    def fake_publish(acc, *a):
        if acc.id == "second":
            raise RuntimeError("X down")
        return app.publish.PublishResult(acc.id, "posted")
    monkeypatch.setattr(app.publish, "publish", fake_publish)

    with pytest.raises(RuntimeError, match="second"):
        app.run(env=ENV, session=object(), riot=object(), champions=object())
    logs = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert any(l["message"] == "publishing failed" and l["account_id"] == "second" for l in logs)


def test_x_credentials_are_read_only_when_a_client_is_needed(monkeypatch):
    reads = []

    class Recording(Secrets):
        def latest(self, name):
            reads.append(name)
            return super().latest(name)
    values = {ENV["SECRET_ACCOUNTS"]: json.dumps([account()]), ENV["SECRET_RIOT_API_KEY"]: "RGAPI-test",
              ENV["SECRET_X_APP_CREDENTIALS"]: json.dumps({"consumer_key": "k", "consumer_secret": "s"})}
    monkeypatch.setattr(app.gcp, "SecretStore", lambda session: Recording(values))
    monkeypatch.setattr(app.gcp, "Bucket", lambda session, name: object())
    monkeypatch.setattr(app.collect, "collect", lambda acc, *a: collect.CollectResult(acc.id, "s", "e"))
    made = []

    def fake_publish(acc, settings, bucket, champions, factory, now):
        made.append(factory(acc))
        return app.publish.PublishResult(acc.id, "posted")
    monkeypatch.setattr(app.publish, "publish", fake_publish)
    monkeypatch.setattr(app, "XClient", lambda creds, x: ("client", creds["consumer_key"], x.root_post_id))

    app.run(env=ENV, session=object(), riot=object(), champions=object())

    assert ENV["SECRET_X_APP_CREDENTIALS"] in reads
    assert made == [("client", "k", "2112236264892313956")]

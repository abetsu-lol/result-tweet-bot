import main


def test_entry_point_runs_the_job(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "run", lambda: calls.append(1) or "ok")
    assert main.daily_job({"data": "e30="}, None) == "ok"
    assert calls == [1]

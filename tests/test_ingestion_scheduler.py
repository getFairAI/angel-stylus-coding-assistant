import ingestion_scheduler as sched


def test_env_bool(monkeypatch):
    monkeypatch.delenv("FLAG", raising=False)
    assert sched._env_bool("FLAG", True) is True
    assert sched._env_bool("FLAG", False) is False
    for truthy in ("1", "true", "YES", "on"):
        monkeypatch.setenv("FLAG", truthy)
        assert sched._env_bool("FLAG", False) is True
    monkeypatch.setenv("FLAG", "no")
    assert sched._env_bool("FLAG", True) is False


def test_interval_seconds(monkeypatch):
    monkeypatch.delenv("INGEST_INTERVAL_SECONDS", raising=False)
    assert sched._interval_seconds() == 86400
    monkeypatch.setenv("INGEST_INTERVAL_SECONDS", "3600")
    assert sched._interval_seconds() == 3600
    monkeypatch.setenv("INGEST_INTERVAL_SECONDS", "5")  # clamped to 60
    assert sched._interval_seconds() == 60
    monkeypatch.setenv("INGEST_INTERVAL_SECONDS", "bad")
    assert sched._interval_seconds() == 86400


def test_run_once_invokes_pipeline(monkeypatch):
    called = {}
    monkeypatch.setattr(sched, "run_all", lambda force_refresh: called.setdefault("force", force_refresh))
    monkeypatch.setenv("INGEST_FORCE_REFRESH", "true")
    sched.run_once()
    assert called["force"] is True


def test_run_once_swallows_errors(monkeypatch):
    def boom(force_refresh):
        raise RuntimeError("scrape failed")

    monkeypatch.setattr(sched, "run_all", boom)
    # Must not raise — the scheduler keeps running.
    sched.run_once()

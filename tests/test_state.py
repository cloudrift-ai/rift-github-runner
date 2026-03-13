from __future__ import annotations

import datetime

from sqlalchemy import create_engine

from rift_github_runner.state import StateStore


def _make_store():
    engine = create_engine("sqlite:///:memory:")
    return StateStore(engine)


def test_try_create_and_get():
    ss = _make_store()
    created = ss.try_create_job(
        job_id=100,
        instance_id="inst-abc",
        run_id=200,
        repo="myorg/myrepo",
        labels=["self-hosted", "cloudrift"],
    )
    assert created is True

    record = ss.get_job(100)
    assert record is not None
    assert record.instance_id == "inst-abc"
    assert record.status == "running"
    assert record.labels == ["self-hosted", "cloudrift"]


def test_duplicate_create_returns_false():
    ss = _make_store()
    ss.try_create_job(job_id=100, instance_id="inst-abc", run_id=200, repo="r", labels=[])
    created = ss.try_create_job(job_id=100, instance_id="inst-xyz", run_id=201, repo="r", labels=[])
    assert created is False


def test_get_nonexistent_returns_none():
    ss = _make_store()
    assert ss.get_job(999) is None


def test_mark_completed():
    ss = _make_store()
    ss.try_create_job(job_id=100, instance_id="inst-abc", run_id=200, repo="r", labels=[])
    ss.mark_completed(100)
    assert ss.get_job(100).status == "completed"


def test_mark_failed():
    ss = _make_store()
    ss.try_create_job(job_id=100, instance_id="inst-abc", run_id=200, repo="r", labels=[])
    ss.mark_failed(100)
    assert ss.get_job(100).status == "failed"


def test_find_stale_jobs():
    ss = _make_store()
    ss.try_create_job(job_id=100, instance_id="inst-abc", run_id=200, repo="r", labels=[])

    # No stale jobs yet (just created)
    stale = ss.find_stale_jobs(max_age_minutes=1)
    assert len(stale) == 0

    # Backdate the record
    from rift_github_runner.state import JobRow, Session

    with Session(ss._engine) as session:
        row = session.get(JobRow, 100)
        row.created_at = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(minutes=10)
        session.commit()

    stale = ss.find_stale_jobs(max_age_minutes=5)
    assert len(stale) == 1
    assert stale[0].job_id == 100


def test_delete_old_jobs():
    ss = _make_store()
    ss.try_create_job(job_id=100, instance_id="inst-abc", run_id=200, repo="r", labels=[])

    # Backdate the record
    from rift_github_runner.state import JobRow, Session

    with Session(ss._engine) as session:
        row = session.get(JobRow, 100)
        row.created_at = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=48)
        session.commit()

    deleted = ss.delete_old_jobs(max_age_hours=24)
    assert deleted == 1
    assert ss.get_job(100) is None

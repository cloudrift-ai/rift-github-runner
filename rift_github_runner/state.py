from __future__ import annotations

import datetime
import json
import logging
import os
from dataclasses import dataclass

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:////app/data/runner_jobs.db"
_TTL_HOURS = 24


class Base(DeclarativeBase):
    pass


class JobRow(Base):
    __tablename__ = "runner_jobs"

    job_id = Column(Integer, primary_key=True)
    instance_id = Column(String, nullable=False)
    run_id = Column(Integer, nullable=False)
    repo = Column(String, nullable=False)
    labels = Column(Text, nullable=False, default="[]")
    status = Column(String, nullable=False, default="running")
    created_at = Column(DateTime(timezone=True), nullable=False)


@dataclass
class JobRecord:
    job_id: int
    instance_id: str
    run_id: int
    repo: str
    labels: list[str]
    status: str
    created_at: datetime.datetime


class StateStore:
    def __init__(self, engine=None):
        if engine is None:
            url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
            engine = create_engine(url)
        self._engine = engine
        Base.metadata.create_all(self._engine)

    def _row_to_record(self, row: JobRow) -> JobRecord:
        return JobRecord(
            job_id=row.job_id,
            instance_id=row.instance_id,
            run_id=row.run_id,
            repo=row.repo,
            labels=json.loads(row.labels),
            status=row.status,
            created_at=row.created_at,
        )

    def try_create_job(
        self,
        job_id: int,
        instance_id: str,
        run_id: int,
        repo: str,
        labels: list[str],
    ) -> bool:
        with Session(self._engine) as session:
            existing = session.get(JobRow, job_id)
            if existing is not None:
                logger.warning("Job %s already exists (duplicate webhook?), skipping", job_id)
                return False
            row = JobRow(
                job_id=job_id,
                instance_id=instance_id,
                run_id=run_id,
                repo=repo,
                labels=json.dumps(labels),
                status="running",
                created_at=datetime.datetime.now(tz=datetime.UTC),
            )
            session.add(row)
            session.commit()
            return True

    def get_job(self, job_id: int) -> JobRecord | None:
        with Session(self._engine) as session:
            row = session.get(JobRow, job_id)
            if row is None:
                return None
            return self._row_to_record(row)

    def mark_completed(self, job_id: int) -> None:
        with Session(self._engine) as session:
            row = session.get(JobRow, job_id)
            if row:
                row.status = "completed"
                session.commit()

    def mark_failed(self, job_id: int) -> None:
        with Session(self._engine) as session:
            row = session.get(JobRow, job_id)
            if row:
                row.status = "failed"
                session.commit()

    def find_stale_jobs(self, max_age_minutes: int) -> list[JobRecord]:
        cutoff = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(
            minutes=max_age_minutes
        )
        with Session(self._engine) as session:
            rows = (
                session.query(JobRow)
                .filter(JobRow.status == "running", JobRow.created_at < cutoff)
                .all()
            )
            return [self._row_to_record(r) for r in rows]

    def delete_old_jobs(self, max_age_hours: int = _TTL_HOURS) -> int:
        cutoff = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(hours=max_age_hours)
        with Session(self._engine) as session:
            count = session.query(JobRow).filter(JobRow.created_at < cutoff).delete()
            session.commit()
            logger.info("Deleted %d old job records", count)
            return count

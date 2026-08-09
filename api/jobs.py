from __future__ import annotations

import threading
import uuid
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Any, Protocol

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .database import SessionLocal
from .db_models import Job, JobStatus, utc_now
from .licensing import AuthenticatedPrincipal


class JobQueue(Protocol):
    def enqueue(self, job_id: uuid.UUID) -> None: ...

    def dequeue(self, *, timeout: int = 5) -> uuid.UUID | None: ...


class RedisJobQueue:
    def __init__(self, client: Redis, queue_name: str) -> None:
        self.client = client
        self.queue_name = queue_name

    def enqueue(self, job_id: uuid.UUID) -> None:
        self.client.rpush(self.queue_name, str(job_id))

    def dequeue(self, *, timeout: int = 5) -> uuid.UUID | None:
        item = self.client.blpop(self.queue_name, timeout=timeout)
        if item is None:
            return None
        raw_id = item[1]
        if isinstance(raw_id, bytes):
            raw_id = raw_id.decode("ascii")
        return uuid.UUID(raw_id)


class InMemoryJobQueue:
    def __init__(self) -> None:
        self._items: deque[uuid.UUID] = deque()
        self._condition = threading.Condition()

    def enqueue(self, job_id: uuid.UUID) -> None:
        with self._condition:
            self._items.append(job_id)
            self._condition.notify()

    def dequeue(self, *, timeout: int = 5) -> uuid.UUID | None:
        with self._condition:
            if not self._items:
                self._condition.wait(timeout=timeout)
            return self._items.popleft() if self._items else None


@dataclass(frozen=True)
class JobStatusView:
    id: uuid.UUID
    kind: str
    status: JobStatus
    result: Mapping[str, Any] | None
    error: str | None
    attempts: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class JobEnqueueError(RuntimeError):
    pass


def enqueue_job(
    session: Session,
    queue: JobQueue,
    kind: str,
    payload: Mapping[str, Any],
    *,
    principal: AuthenticatedPrincipal | None = None,
    idempotency_key: str | None = None,
    max_attempts: int = 3,
) -> Job:
    """Persist a job before publishing it; this operation commits the supplied session."""
    if not kind.strip():
        raise ValueError("job kind is required")
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least one")
    idempotency_scope = f"user:{principal.user_id}" if principal else "system"
    if idempotency_key:
        existing = session.scalar(
            select(Job).where(
                Job.idempotency_scope == idempotency_scope,
                Job.kind == kind.strip(),
                Job.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing

    job = Job(
        user_id=principal.user_id if principal else None,
        license_id=principal.license_id if principal else None,
        kind=kind.strip(),
        payload=dict(payload),
        idempotency_scope=idempotency_scope if idempotency_key else None,
        idempotency_key=idempotency_key,
        max_attempts=max_attempts,
    )
    session.add(job)
    session.commit()
    try:
        queue.enqueue(job.id)
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.error = "Could not enqueue job"
        job.finished_at = utc_now()
        session.commit()
        raise JobEnqueueError("could not enqueue persisted job") from exc
    return job


def get_job_status(
    session: Session,
    job_id: uuid.UUID,
    *,
    principal: AuthenticatedPrincipal | None = None,
) -> JobStatusView | None:
    job = session.get(Job, job_id)
    if job is None:
        return None
    if principal is not None and job.user_id != principal.user_id:
        return None
    return JobStatusView(
        id=job.id,
        kind=job.kind,
        status=job.status,
        result=job.result,
        error=job.error,
        attempts=job.attempts,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def cancel_job(
    session: Session,
    job_id: uuid.UUID,
    *,
    principal: AuthenticatedPrincipal | None = None,
) -> bool:
    job = session.get(Job, job_id)
    if job is None or (principal is not None and job.user_id != principal.user_id):
        return False
    if job.status != JobStatus.QUEUED:
        return False
    job.status = JobStatus.CANCELLED
    job.finished_at = utc_now()
    session.commit()
    return True


JobHandler = Callable[[dict[str, Any]], Mapping[str, Any] | None]


def process_next_job(
    session_factory: sessionmaker[Session],
    queue: JobQueue,
    handlers: Mapping[str, JobHandler],
    *,
    timeout: int = 5,
) -> bool:
    job_id = queue.dequeue(timeout=timeout)
    if job_id is None:
        return False

    with session_factory() as session:
        job = session.scalar(select(Job).where(Job.id == job_id).with_for_update())
        if job is None or job.status != JobStatus.QUEUED:
            return True
        handler = handlers.get(job.kind)
        if handler is None:
            job.status = JobStatus.FAILED
            job.error = f"No worker handler registered for job kind: {job.kind}"
            job.finished_at = utc_now()
            session.commit()
            return True
        job.status = JobStatus.RUNNING
        job.attempts += 1
        job.started_at = utc_now()
        session.commit()

        try:
            result = handler(dict(job.payload))
            job.result = dict(result) if result is not None else {}
            job.error = None
            job.status = JobStatus.SUCCEEDED
            job.finished_at = utc_now()
            session.commit()
        except Exception as exc:
            session.rollback()
            job = session.get(Job, job_id)
            if job is None:
                raise
            job.error = str(exc)[:4000] or exc.__class__.__name__
            if job.attempts < job.max_attempts:
                job.status = JobStatus.QUEUED
                session.commit()
                try:
                    queue.enqueue(job.id)
                except Exception as enqueue_error:
                    job.status = JobStatus.FAILED
                    job.error = "Could not re-enqueue failed job"
                    job.finished_at = utc_now()
                    session.commit()
                    raise JobEnqueueError("could not re-enqueue failed job") from enqueue_error
            else:
                job.status = JobStatus.FAILED
                job.finished_at = utc_now()
                session.commit()
        return True


def create_job_queue(
    settings: Settings | None = None,
    *,
    redis_client: Redis | None = None,
) -> RedisJobQueue:
    resolved = settings or get_settings()
    client = redis_client or Redis.from_url(resolved.redis_url, decode_responses=True)
    client.ping()
    return RedisJobQueue(client, resolved.job_queue_name)


@lru_cache
def get_job_queue() -> RedisJobQueue:
    return create_job_queue()


def run_worker(
    *,
    stop_event: threading.Event,
    queue: JobQueue | None = None,
    session_factory: sessionmaker[Session] = SessionLocal,
    handlers: Mapping[str, JobHandler] | None = None,
    poll_timeout: int | None = None,
) -> None:
    settings = get_settings()
    resolved_queue = queue or get_job_queue()
    resolved_handlers = handlers or {}
    timeout = poll_timeout or settings.worker_poll_timeout_seconds
    while not stop_event.is_set():
        process_next_job(
            session_factory,
            resolved_queue,
            resolved_handlers,
            timeout=timeout,
        )

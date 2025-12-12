import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional


@dataclass
class JobStatus:
    id: str
    type: str
    status: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    detail: Optional[str] = None


class JobRegistry:
    def __init__(self):
        self._jobs: Dict[str, JobStatus] = {}

    def create(self, job_id: str, job_type: str) -> JobStatus:
        job = JobStatus(id=job_id, type=job_type, status="pending")
        self._jobs[job_id] = job
        return job

    def update(self, job_id: str, status: str, detail: Optional[str] = None) -> JobStatus:
        job = self._jobs[job_id]
        job.status = status
        job.updated_at = datetime.utcnow()
        job.detail = detail
        return job

    def get(self, job_id: str) -> Optional[JobStatus]:
        return self._jobs.get(job_id)


registry = JobRegistry()


async def simulate_long_running(job_id: str, coro):
    registry.update(job_id, "running")
    try:
        await asyncio.sleep(0.1)
        await coro
        registry.update(job_id, "succeeded")
    except Exception as exc:  # noqa: BLE001
        registry.update(job_id, "failed", detail=str(exc))
        raise

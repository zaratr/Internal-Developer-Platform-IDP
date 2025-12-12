import uuid
from typing import List

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditAction, Deployment, DeploymentStatus, Environment, Service
from app.platform.guardrails import GuardrailEngine
from app.schemas.domain import DeploymentTriggerRequest
from app.services.audit import log_action
from app.services.jobs import registry, simulate_long_running


guardrails = GuardrailEngine()


async def trigger_deployment(
    db: AsyncSession,
    *,
    service_id: int,
    environment_id: int,
    payload: DeploymentTriggerRequest,
    background_tasks: BackgroundTasks,
    approvals: List[str],
    performed_by: str,
) -> str:
    service = await db.get(Service, service_id)
    environment = await db.get(Environment, environment_id)
    if not service or not environment or environment.service_id != service.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service or environment not found")

    # idempotent check: avoid duplicate version deployment per env
    existing = await db.scalar(
        select(Deployment).where(
            Deployment.service_id == service.id,
            Deployment.environment_id == environment.id,
            Deployment.version == payload.version,
        )
    )
    if existing:
        return f"deployment-{existing.id}"  # idempotent response

    deployment = Deployment(
        service=service,
        environment=environment,
        version=payload.version,
        status=DeploymentStatus.pending,
        initiated_by=payload.initiated_by,
    )
    guardrails.validate_production_deployment(deployment, approvals)

    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    job_id = f"deployment-{deployment.id}" or str(uuid.uuid4())
    registry.create(job_id, "deployment")

    async def execute():
        deployment.status = DeploymentStatus.running
        await db.commit()
        await log_action(
            db,
            action=AuditAction.updated,
            entity_type="deployment",
            entity_id=str(deployment.id),
            performed_by=performed_by,
            metadata={"status": deployment.status.value},
        )
        deployment.status = DeploymentStatus.succeeded
        await db.commit()
        await db.refresh(deployment)
        await log_action(
            db,
            action=AuditAction.updated,
            entity_type="deployment",
            entity_id=str(deployment.id),
            performed_by=performed_by,
            metadata={"status": deployment.status.value},
        )

    background_tasks.add_task(simulate_long_running, job_id, execute())
    await log_action(
        db,
        action=AuditAction.created,
        entity_type="deployment",
        entity_id=str(deployment.id),
        performed_by=performed_by,
        metadata={"version": payload.version},
    )
    return job_id


async def get_deployment_history(db: AsyncSession, service_id: int) -> List[Deployment]:
    result = await db.execute(select(Deployment).where(Deployment.service_id == service_id))
    return result.scalars().all()

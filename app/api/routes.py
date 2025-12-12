from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from prometheus_client import Counter, Histogram, generate_latest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import Role, UserContext, get_current_user, require_roles
from app.db.session import get_db
from app.models.models import AuditLog, Deployment, Environment, Service, Team
from app.schemas.domain import (
    AuditLogRead,
    DeploymentRead,
    DeploymentTriggerRequest,
    EnvironmentProvisionRequest,
    EnvironmentRead,
    PolicyRead,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
    TeamCreate,
    TeamRead,
)
from app.services import deployment as deployment_service
from app.services import service as service_service

router = APIRouter()

request_latency = Histogram("api_latency_seconds", "API latency", ["endpoint"])
failed_operations = Counter("api_failed_operations_total", "Failed operations", ["endpoint"])
job_duration = Histogram("job_duration_seconds", "Async job duration", ["job_type"])


@router.post("/teams", response_model=TeamRead)
async def create_team(
    payload: TeamCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_roles(Role.PLATFORM_ADMIN, Role.TEAM_ADMIN)),
):
    with request_latency.labels("create_team").time():
        return await service_service.create_team(db, payload.name, payload.description)


@router.post("/services", response_model=ServiceRead, status_code=status.HTTP_201_CREATED)
async def register_service(
    payload: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_roles(Role.PLATFORM_ADMIN, Role.DEVELOPER, Role.TEAM_ADMIN)),
):
    with request_latency.labels("register_service").time():
        try:
            return await service_service.register_service(db, payload, performed_by=user.username)
        except HTTPException:
            failed_operations.labels("register_service").inc()
            raise


@router.patch("/services/{service_id}", response_model=ServiceRead)
async def update_service(
    service_id: int,
    payload: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_roles(Role.PLATFORM_ADMIN, Role.TEAM_ADMIN)),
):
    with request_latency.labels("update_service").time():
        return await service_service.update_service(db, service_id, payload, performed_by=user.username)


@router.post("/services/{service_id}/team", response_model=ServiceRead)
async def assign_team(
    service_id: int,
    team_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_roles(Role.PLATFORM_ADMIN, Role.TEAM_ADMIN)),
):
    with request_latency.labels("assign_team").time():
        return await service_service.assign_service_team(db, service_id, team_id, performed_by=user.username)


@router.post("/services/{service_id}/environments", response_model=EnvironmentRead, status_code=status.HTTP_201_CREATED)
async def provision_environment(
    service_id: int,
    payload: EnvironmentProvisionRequest,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_roles(Role.PLATFORM_ADMIN, Role.TEAM_ADMIN)),
):
    with request_latency.labels("provision_environment").time():
        return await service_service.provision_environment(db, service_id, payload, performed_by=user.username)


@router.post(
    "/services/{service_id}/environments/{environment_id}/deployments",
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_deployment(
    service_id: int,
    environment_id: int,
    payload: DeploymentTriggerRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_roles(Role.PLATFORM_ADMIN, Role.DEVELOPER, Role.TEAM_ADMIN)),
):
    with request_latency.labels("trigger_deployment").time():
        job_id = await deployment_service.trigger_deployment(
            db,
            service_id=service_id,
            environment_id=environment_id,
            payload=payload,
            background_tasks=background_tasks,
            approvals=[user.username] if user.role == Role.PLATFORM_ADMIN else [],
            performed_by=user.username,
        )
        return {"job_id": job_id}


@router.get("/services/{service_id}/deployments", response_model=List[DeploymentRead])
async def list_deployment_history(
    service_id: int,
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    deployments = await deployment_service.get_deployment_history(db, service_id)
    return deployments


@router.get("/audit", response_model=List[AuditLogRead])
async def get_audit_logs(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(require_roles(Role.PLATFORM_ADMIN, Role.TEAM_ADMIN)),
):
    result = await db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()))
    return result.scalars().all()


@router.get("/metrics")
async def metrics():
    return generate_latest()


@router.get("/services", response_model=List[ServiceRead])
async def list_services(db: AsyncSession = Depends(get_db), user: UserContext = Depends(get_current_user)):
    result = await db.execute(select(Service))
    return result.scalars().all()


@router.get("/teams", response_model=List[TeamRead])
async def list_teams(db: AsyncSession = Depends(get_db), user: UserContext = Depends(get_current_user)):
    result = await db.execute(select(Team))
    return result.scalars().all()


@router.get("/services/{service_id}/environments", response_model=List[EnvironmentRead])
async def list_envs(service_id: int, db: AsyncSession = Depends(get_db), user: UserContext = Depends(get_current_user)):
    result = await db.execute(select(Environment).where(Environment.service_id == service_id))
    return result.scalars().all()

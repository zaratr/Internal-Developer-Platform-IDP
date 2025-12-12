from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditAction, Environment, EnvironmentTier, Service, Team
from app.platform.guardrails import GuardrailEngine
from app.schemas.domain import EnvironmentProvisionRequest, ServiceCreate, ServiceUpdate
from app.services.audit import log_action


guardrails = GuardrailEngine()


async def create_team(db: AsyncSession, name: str, description: Optional[str]) -> Team:
    existing = await db.scalar(select(Team).where(Team.name == name))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Team already exists")
    team = Team(name=name, description=description)
    db.add(team)
    await db.commit()
    await db.refresh(team)
    return team


async def register_service(db: AsyncSession, payload: ServiceCreate, performed_by: str) -> Service:
    existing = await db.scalar(select(Service).where(Service.name == payload.name))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Service already exists")
    guardrails.validate_service_tags(payload.tags)
    service = Service(name=payload.name, description=payload.description, tags=payload.tags)
    db.add(service)
    await db.commit()
    await db.refresh(service)
    await log_action(
        db,
        action=AuditAction.created,
        entity_type="service",
        entity_id=str(service.id),
        performed_by=performed_by,
        metadata={"name": service.name},
    )
    return service


async def assign_service_team(
    db: AsyncSession, service_id: int, team_id: int, performed_by: str
) -> Service:
    service = await db.get(Service, service_id)
    team = await db.get(Team, team_id)
    if not service or not team:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service or team not found")
    service.team = team
    await db.commit()
    await db.refresh(service)
    await log_action(
        db,
        action=AuditAction.updated,
        entity_type="service",
        entity_id=str(service.id),
        performed_by=performed_by,
        metadata={"team_id": team_id},
    )
    return service


async def provision_environment(
    db: AsyncSession, service_id: int, req: EnvironmentProvisionRequest, performed_by: str
) -> Environment:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    guardrails.validate_service_tags(service.tags)
    guardrails.validate_environment_promotion([env.tier.value for env in service.environments], req.tier)
    guardrails.validate_config(req.config)
    environment = Environment(
        name=req.name, tier=req.tier, service=service, config=req.config
    )
    db.add(environment)
    await db.commit()
    await db.refresh(environment)
    await log_action(
        db,
        action=AuditAction.created,
        entity_type="environment",
        entity_id=str(environment.id),
        performed_by=performed_by,
        metadata={"tier": req.tier.value},
    )
    return environment


async def list_deployments(db: AsyncSession, service_id: int) -> List:
    result = await db.execute(select(Environment).where(Environment.service_id == service_id))
    return result.scalars().all()


async def update_service(db: AsyncSession, service_id: int, payload: ServiceUpdate, performed_by: str) -> Service:
    service = await db.get(Service, service_id)
    if not service:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    if payload.description is not None:
        service.description = payload.description
    if payload.tags is not None:
        guardrails.validate_service_tags(payload.tags)
        service.tags = payload.tags
    if payload.team_id is not None:
        team = await db.get(Team, payload.team_id)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
        service.team = team
    await db.commit()
    await db.refresh(service)
    await log_action(
        db,
        action=AuditAction.updated,
        entity_type="service",
        entity_id=str(service.id),
        performed_by=performed_by,
        metadata={"updated": True},
    )
    return service

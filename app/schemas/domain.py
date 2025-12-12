from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.models import AuditAction, DeploymentStatus, EnvironmentTier


class TeamCreate(BaseModel):
    name: str
    description: Optional[str] = None


class TeamRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Dict[str, str] = Field(default_factory=dict)


class ServiceUpdate(BaseModel):
    description: Optional[str] = None
    tags: Optional[Dict[str, str]] = None
    team_id: Optional[int] = None


class ServiceRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    team_id: Optional[int]
    tags: Dict[str, str]
    created_at: datetime

    class Config:
        from_attributes = True


class EnvironmentProvisionRequest(BaseModel):
    name: str
    tier: EnvironmentTier
    config: Dict[str, Any] = Field(default_factory=dict)


class EnvironmentRead(BaseModel):
    id: int
    name: str
    tier: EnvironmentTier
    config: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class DeploymentTriggerRequest(BaseModel):
    version: str
    initiated_by: str


class DeploymentRead(BaseModel):
    id: int
    service_id: int
    environment_id: int
    version: str
    status: DeploymentStatus
    initiated_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AuditLogRead(BaseModel):
    id: int
    action: AuditAction
    entity_type: str
    entity_id: str
    performed_by: str
    metadata: Dict[str, Any]
    created_at: datetime

    class Config:
        from_attributes = True


class PolicyRead(BaseModel):
    id: int
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    enforced: bool

    class Config:
        from_attributes = True

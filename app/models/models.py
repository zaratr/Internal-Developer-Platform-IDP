import enum
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EnvironmentTier(str, enum.Enum):
    dev = "dev"
    staging = "staging"
    prod = "prod"


class DeploymentStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class AuditAction(str, enum.Enum):
    created = "created"
    updated = "updated"
    deleted = "deleted"
    guardrail_blocked = "guardrail_blocked"


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    services: Mapped[list["Service"]] = relationship(back_populates="team")


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    team_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"))
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    tags: Mapped[Dict[str, str]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    team: Mapped[Optional[Team]] = relationship(back_populates="services")
    environments: Mapped[list["Environment"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="service", cascade="all, delete-orphan"
    )


class Environment(Base):
    __tablename__ = "environments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    tier: Mapped[EnvironmentTier] = mapped_column(Enum(EnvironmentTier), nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    service: Mapped[Service] = relationship(back_populates="environments")
    deployments: Mapped[list["Deployment"]] = relationship(
        back_populates="environment", cascade="all, delete-orphan"
    )


class Deployment(Base):
    __tablename__ = "deployments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    environment_id: Mapped[int] = mapped_column(ForeignKey("environments.id"))
    version: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DeploymentStatus] = mapped_column(
        Enum(DeploymentStatus), default=DeploymentStatus.pending
    )
    initiated_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    service: Mapped[Service] = relationship(back_populates="deployments")
    environment: Mapped[Environment] = relationship(back_populates="deployments")


class PlatformPolicy(Base):
    __tablename__ = "platform_policies"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

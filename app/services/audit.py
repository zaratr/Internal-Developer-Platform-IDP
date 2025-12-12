from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AuditAction, AuditLog


async def log_action(
    db: AsyncSession, *, action: AuditAction, entity_type: str, entity_id: str, performed_by: str, metadata: Dict[str, Any]
) -> AuditLog:
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        performed_by=performed_by,
        metadata=metadata,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return entry

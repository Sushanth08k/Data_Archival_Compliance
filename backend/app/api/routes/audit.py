"""
Audit evidence routes — list and filter audit events.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.audit import AuditEvidence
from app.schemas.policy import AuditEvidenceResponse

router = APIRouter(prefix="/audit-evidence", tags=["Audit Evidence"])


@router.get("")
async def list_audit_evidence(
    policy_id: str = Query(None),
    control_run_id: str = Query(None),
    event_type: str = Query(None),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List audit evidence with optional filters."""
    query = select(AuditEvidence).order_by(AuditEvidence.timestamp.desc())

    if policy_id:
        query = query.where(AuditEvidence.policy_id == policy_id)
    if control_run_id:
        query = query.where(AuditEvidence.control_run_id == control_run_id)
    if event_type:
        query = query.where(AuditEvidence.event_type == event_type)

    query = query.limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return {
        "events": [AuditEvidenceResponse.model_validate(e) for e in events],
        "total": len(events),
    }

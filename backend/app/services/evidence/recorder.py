"""
Audit evidence recorder — creates immutable audit log entries.
"""

import json
import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvidence

logger = logging.getLogger(__name__)


async def record_event(
    db: AsyncSession,
    event_type: str,
    actor_id: Optional[str] = None,
    actor_email: Optional[str] = None,
    policy_id: Optional[str] = None,
    policy_version_id: Optional[str] = None,
    control_run_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> AuditEvidence:
    """Record an audit evidence event."""
    evidence = AuditEvidence(
        event_type=event_type,
        actor_id=actor_id,
        actor_email=actor_email,
        policy_id=policy_id,
        policy_version_id=policy_version_id,
        control_run_id=control_run_id,
        metadata_json=json.dumps(metadata) if metadata else None,
    )
    db.add(evidence)
    await db.flush()
    logger.info(f"Audit: {event_type} by={actor_email} policy={policy_id}")
    return evidence

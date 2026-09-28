"""
AuditEvidence model — immutable log of every significant compliance action.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditEvidence(Base):
    __tablename__ = "audit_evidence"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(36), nullable=True)
    actor_email: Mapped[str] = mapped_column(String(255), nullable=True)
    policy_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    policy_version_id: Mapped[str] = mapped_column(String(36), nullable=True)
    control_run_id: Mapped[str] = mapped_column(String(36), nullable=True, index=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=True)  # JSON blob
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    def __repr__(self) -> str:
        return f"<AuditEvidence {self.event_type} at {self.timestamp}>"

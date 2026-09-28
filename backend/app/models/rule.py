"""
PolicyRule and PolicyException models — structured, machine-executable rules
extracted from policy documents by the LLM.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer, Float, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PolicyRule(Base):
    __tablename__ = "policy_rules"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    policy_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("policy_versions.id"), nullable=False
    )
    rule_id: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. RULE-001
    rule_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="RETENTION"
    )  # RETENTION, ARCHIVAL, VERIFICATION
    description: Mapped[str] = mapped_column(Text, nullable=True)
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(50), nullable=False)  # OLDER_THAN, EQUALS, GREATER_THAN, etc.
    value: Mapped[str] = mapped_column(String(255), nullable=False)  # stored as string, cast at evaluation
    unit: Mapped[str] = mapped_column(String(50), nullable=True)  # years, months, days, etc.
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # ARCHIVE, EXCLUDE, VERIFY, DELETE
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_errors: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    policy_version = relationship("PolicyVersion", back_populates="rules")

    def __repr__(self) -> str:
        return f"<PolicyRule {self.rule_id} {self.field} {self.operator} {self.value}>"


class PolicyException(Base):
    __tablename__ = "policy_exceptions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    policy_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("policy_versions.id"), nullable=False
    )
    field: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, default="EXCLUDE"
    )
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    policy_version = relationship("PolicyVersion", back_populates="exceptions")

    def __repr__(self) -> str:
        return f"<PolicyException {self.field} {self.operator} {self.value}>"

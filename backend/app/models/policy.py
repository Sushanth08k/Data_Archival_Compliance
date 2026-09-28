"""
Policy and PolicyVersion models — core entities for the policy lifecycle.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True, default="")
    scope: Mapped[str] = mapped_column(String(255), nullable=True, default="")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="DRAFT"
    )  # DRAFT, ACTIVE, ARCHIVED
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    versions = relationship("PolicyVersion", back_populates="policy", order_by="PolicyVersion.version.desc()")

    def __repr__(self) -> str:
        return f"<Policy {self.name} status={self.status}>"


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("policies.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    document_path: Mapped[str] = mapped_column(String(500), nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=True)
    analysis_result: Mapped[str] = mapped_column(Text, nullable=True)  # JSON string
    analysis_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING"
    )  # PENDING, EXTRACTING, ANALYZING, COMPLETED, FAILED
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    policy = relationship("Policy", back_populates="versions")
    rules = relationship("PolicyRule", back_populates="policy_version")
    exceptions = relationship("PolicyException", back_populates="policy_version")

    def __repr__(self) -> str:
        return f"<PolicyVersion policy={self.policy_id} v={self.version}>"

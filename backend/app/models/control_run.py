"""
ControlRun and ControlRunRecord models — track execution of compliance controls.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, Integer, Boolean, ForeignKey, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ControlRun(Base):
    __tablename__ = "control_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    policy_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("policies.id"), nullable=False
    )
    policy_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("policy_versions.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING"
    )  # PENDING, EVALUATING, ARCHIVING, VERIFYING, AWAITING_APPROVAL, APPROVED, CLEANING, FINAL_VERIFICATION, COMPLETED, FAILED

    # Counts
    total_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eligible_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    excluded_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archived_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cleaned_records: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Generated SQL scripts
    generated_sql: Mapped[str] = mapped_column(Text, nullable=True)  # Selection / Inspection SQL
    archival_sql: Mapped[str] = mapped_column(Text, nullable=True)   # Insert into archive SQL
    cleanup_sql: Mapped[str] = mapped_column(Text, nullable=True)    # Approved Delete from source SQL


    # Database Profile
    target_database: Mapped[str] = mapped_column(String(100), nullable=True, default="Default Compliance DB (SQLite)")
    database_dialect: Mapped[str] = mapped_column(String(50), nullable=True, default="sqlite")

    # Timestamps
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    policy = relationship("Policy")
    policy_version = relationship("PolicyVersion")
    records = relationship("ControlRunRecord", back_populates="control_run", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ControlRun {self.id[:8]} status={self.status}>"


class ControlRunRecord(Base):
    __tablename__ = "control_run_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    control_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("control_runs.id"), nullable=False
    )
    record_identifier: Mapped[str] = mapped_column(String(100), nullable=False)  # simulated record ID
    record_data: Mapped[str] = mapped_column(Text, nullable=True)  # JSON blob of the simulated record
    matched_rule_id: Mapped[str] = mapped_column(String(50), nullable=True)  # which rule matched

    # Lifecycle flags
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_excluded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exclusion_reason: Mapped[str] = mapped_column(Text, nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_cleaned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_final_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    control_run = relationship("ControlRun", back_populates="records")

    def __repr__(self) -> str:
        return f"<ControlRunRecord {self.record_identifier} eligible={self.is_eligible}>"


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    control_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("control_runs.id"), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING"
    )  # PENDING, APPROVED, REJECTED

    # Request details
    requested_by: Mapped[str] = mapped_column(String(36), nullable=False)
    requested_by_email: Mapped[str] = mapped_column(String(255), nullable=True)
    records_to_cleanup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str] = mapped_column(Text, nullable=True)

    # Review
    reviewed_by: Mapped[str] = mapped_column(String(36), nullable=True)
    reviewed_by_email: Mapped[str] = mapped_column(String(255), nullable=True)
    review_comments: Mapped[str] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    control_run = relationship("ControlRun")

    def __repr__(self) -> str:
        return f"<ApprovalRequest run={self.control_run_id[:8]} status={self.status}>"

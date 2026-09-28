"""
Transaction models — represents real core banking records in Active and Archive databases.
"""

from datetime import datetime, timezone
from sqlalchemy import String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourceTransaction(Base):
    """
    Active database records table — Core Banking System.
    Subject to policy evaluation, archival, and controlled source cleanup.
    """
    __tablename__ = "source_transactions"

    transaction_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_date: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # ISO string or YYYY-MM-DD
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False, default="WIRE")  # WIRE, ACH, DEBIT, CREDIT
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "account_id": self.account_id,
            "customer_name": self.customer_name,
            "transaction_date": self.transaction_date,
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "legal_hold": self.legal_hold,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ArchiveTransaction(Base):
    """
    Approved Archival Database records table.
    Stores archived copies of records independently verified before source cleanup.
    """
    __tablename__ = "archive_transactions"

    transaction_id: Mapped[str] = mapped_column(String(50), primary_key=True, index=True)
    account_id: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_date: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False, default="WIRE")
    legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ARCHIVED")
    
    # Archival audit tracking
    control_run_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    verification_hash: Mapped[str] = mapped_column(String(128), nullable=True)
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "account_id": self.account_id,
            "customer_name": self.customer_name,
            "transaction_date": self.transaction_date,
            "amount": self.amount,
            "transaction_type": self.transaction_type,
            "legal_hold": self.legal_hold,
            "status": self.status,
            "control_run_id": self.control_run_id,
            "verification_hash": self.verification_hash,
            "archived_at": self.archived_at.isoformat() if self.archived_at else None,
        }

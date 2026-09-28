"""
Pydantic schemas for control runs, approval requests, and real database tables.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


# --- Database Records ---

class TransactionRecordResponse(BaseModel):
    transaction_id: str
    account_id: str
    customer_name: str
    transaction_date: str
    amount: float
    transaction_type: str
    legal_hold: bool
    status: str
    created_at: Optional[str] = None
    # Archive-specific fields
    control_run_id: Optional[str] = None
    verification_hash: Optional[str] = None
    archived_at: Optional[str] = None

    model_config = {"from_attributes": True}


class DatabaseProfileResponse(BaseModel):
    id: str
    name: str
    dialect: str
    host: str
    database: str
    description: str
    tables: list[str]
    is_active: bool = False
    color: Optional[str] = None
    icon: Optional[str] = None


class DatabaseViewResponse(BaseModel):
    table_name: str
    total_count: int
    records: list[TransactionRecordResponse]


# --- Control Run ---

class ControlRunResponse(BaseModel):
    id: str
    policy_id: str
    policy_version_id: str
    status: str
    total_records: int = 0
    eligible_records: int = 0
    excluded_records: int = 0
    archived_records: int = 0
    verified_records: int = 0
    cleaned_records: int = 0
    generated_sql: Optional[str] = None
    archival_sql: Optional[str] = None
    cleanup_sql: Optional[str] = None
    target_database: Optional[str] = None
    database_dialect: Optional[str] = None
    created_by: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    policy_name: Optional[str] = None

    model_config = {"from_attributes": True}


class ControlRunListResponse(BaseModel):
    runs: list[ControlRunResponse]
    total: int


class ControlRunRecordResponse(BaseModel):
    id: str
    record_identifier: str
    record_data: Optional[str] = None
    matched_rule_id: Optional[str] = None
    is_eligible: bool = False
    is_excluded: bool = False
    exclusion_reason: Optional[str] = None
    is_archived: bool = False
    is_verified: bool = False
    is_cleaned: bool = False
    is_final_verified: bool = False

    model_config = {"from_attributes": True}


class ControlRunDetailResponse(BaseModel):
    run: ControlRunResponse
    records: list[ControlRunRecordResponse] = []
    verification_issues: list[str] = []
    approval_id: Optional[str] = None


# --- Approval ---

class ApprovalRequestResponse(BaseModel):
    id: str
    control_run_id: str
    status: str
    requested_by: str
    requested_by_email: Optional[str] = None
    records_to_cleanup: int = 0
    summary: Optional[str] = None
    cleanup_sql: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_by_email: Optional[str] = None
    review_comments: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    # Joined fields
    policy_name: Optional[str] = None
    run_status: Optional[str] = None

    model_config = {"from_attributes": True}


class ApprovalListResponse(BaseModel):
    approvals: list[ApprovalRequestResponse]
    total: int


class ApprovalDecisionRequest(BaseModel):
    decision: str  # "APPROVED" or "REJECTED"
    comments: Optional[str] = None

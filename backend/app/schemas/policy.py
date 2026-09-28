"""
Pydantic schemas for policies, rules, and analysis responses.
"""

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


# --- Policy ---

class PolicyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    scope: Optional[str] = ""
    status: str
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PolicyListResponse(BaseModel):
    policies: list[PolicyResponse]
    total: int


# --- PolicyVersion ---

class PolicyVersionResponse(BaseModel):
    id: str
    policy_id: str
    version: int
    document_name: str
    analysis_status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Rules ---

class RuleCondition(BaseModel):
    field: str
    operator: str
    value: Any
    unit: Optional[str] = None


class RuleResponse(BaseModel):
    id: str
    rule_id: str
    rule_type: str
    description: Optional[str] = ""
    field: str
    operator: str
    value: str
    unit: Optional[str] = None
    action: str
    priority: int
    is_valid: bool
    validation_errors: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Exceptions ---

class ExceptionResponse(BaseModel):
    id: str
    field: str
    operator: str
    value: str
    action: str
    description: Optional[str] = ""
    created_at: datetime

    model_config = {"from_attributes": True}


# --- Analysis ---

class AmbiguityItem(BaseModel):
    type: str
    severity: str
    description: str
    requires_human_review: bool = True


class AnalysisResponse(BaseModel):
    policy_version_id: str
    analysis_status: str
    policy_name: Optional[str] = None
    scope: Optional[str] = None
    description: Optional[str] = None
    rules_count: int = 0
    exceptions_count: int = 0
    ambiguities_count: int = 0
    rules: list[RuleResponse] = []
    exceptions: list[ExceptionResponse] = []
    ambiguities: list[AmbiguityItem] = []
    requirements: list[dict] = []


# --- Upload ---

class PolicyUploadResponse(BaseModel):
    policy_id: str
    policy_version_id: str
    document_name: str
    message: str


# --- Audit Evidence ---

class AuditEvidenceResponse(BaseModel):
    id: str
    event_type: str
    actor_email: Optional[str] = None
    policy_id: Optional[str] = None
    policy_version_id: Optional[str] = None
    control_run_id: Optional[str] = None
    metadata_json: Optional[str] = None
    timestamp: datetime

    model_config = {"from_attributes": True}

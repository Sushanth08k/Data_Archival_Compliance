"""
Approvals routes — list pending approval requests, review SQL, and approve or reject.
"""

import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.policy import Policy
from app.models.control_run import ControlRun, ApprovalRequest
from app.schemas.control_run import (
    ApprovalRequestResponse,
    ApprovalListResponse,
    ApprovalDecisionRequest,
)
from app.services.evidence.recorder import record_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("", response_model=ApprovalListResponse)
async def list_approvals(
    status: str = Query(None, description="Filter by status: PENDING, APPROVED, REJECTED"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List approval requests with joined policy and SQL query details."""
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if status:
        query = query.where(ApprovalRequest.status == status.upper())

    result = await db.execute(query)
    approvals = result.scalars().all()

    responses = []
    for app in approvals:
        run = await db.get(ControlRun, app.control_run_id)
        policy_name = None
        cleanup_sql = None
        run_status = None
        if run:
            policy = await db.get(Policy, run.policy_id)
            policy_name = policy.name if policy else None
            cleanup_sql = run.cleanup_sql
            run_status = run.status

        resp = ApprovalRequestResponse.model_validate(app)
        resp.policy_name = policy_name
        resp.cleanup_sql = cleanup_sql
        resp.run_status = run_status
        responses.append(resp)

    return ApprovalListResponse(approvals=responses, total=len(responses))


@router.get("/{approval_id}", response_model=ApprovalRequestResponse)
async def get_approval(
    approval_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get single approval request with its cleanup SQL preview."""
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")

    run = await db.get(ControlRun, approval.control_run_id)
    policy_name = None
    cleanup_sql = None
    run_status = None
    if run:
        policy = await db.get(Policy, run.policy_id)
        policy_name = policy.name if policy else None
        cleanup_sql = run.cleanup_sql
        run_status = run.status

    resp = ApprovalRequestResponse.model_validate(approval)
    resp.policy_name = policy_name
    resp.cleanup_sql = cleanup_sql
    resp.run_status = run_status
    return resp


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    payload: ApprovalDecisionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve or reject a cleanup request."""
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"Request is already {approval.status}")

    decision = payload.decision.upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise HTTPException(status_code=400, detail="Decision must be APPROVED or REJECTED")

    now = datetime.now(timezone.utc)
    approval.status = decision
    approval.reviewed_by = current_user.id
    approval.reviewed_by_email = current_user.email
    approval.review_comments = payload.comments or ""
    approval.reviewed_at = now

    run = await db.get(ControlRun, approval.control_run_id)
    if run:
        if decision == "APPROVED":
            run.status = "APPROVED"
        else:
            run.status = "FAILED"

    await db.commit()

    # Record audit evidence
    event_type = "APPROVAL_GRANTED" if decision == "APPROVED" else "APPROVAL_REJECTED"
    await record_event(
        db=db,
        event_type=event_type,
        actor_id=current_user.id,
        actor_email=current_user.email,
        policy_id=run.policy_id if run else None,
        control_run_id=approval.control_run_id,
        metadata={
            "approval_id": approval.id,
            "decision": decision,
            "comments": payload.comments,
            "records_to_cleanup": approval.records_to_cleanup,
        },
    )

    return {
        "approval_id": approval.id,
        "status": decision,
        "control_run_id": approval.control_run_id,
        "message": f"Approval request {decision.lower()} successfully. Ready to execute cleanup query on database.",
    }

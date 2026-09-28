"""
Control Runs routes — start, list, get details, advance through lifecycle stages,
and inspect the live Active (source_transactions) and Archive (archive_transactions) databases.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, delete

from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.policy import Policy, PolicyVersion
from app.models.rule import PolicyRule, PolicyException
from app.models.control_run import ControlRun, ControlRunRecord, ApprovalRequest
from app.models.transaction import SourceTransaction, ArchiveTransaction
from app.schemas.control_run import (
    ControlRunResponse,
    ControlRunListResponse,
    ControlRunDetailResponse,
    ControlRunRecordResponse,
    ApprovalRequestResponse,
    ApprovalListResponse,
    ApprovalDecisionRequest,
    DatabaseViewResponse,
    TransactionRecordResponse,
    DatabaseProfileResponse,
)
from app.engines.rule_engine import evaluate_records
from app.engines.lifecycle import (
    archive_eligible_records,
    verify_archived_records,
    cleanup_approved_records,
    final_verify_cleanup,
)
from app.services.database_seeder import seed_source_database
from app.services.sql_generator import generate_sql_queries
from app.services.database_profiles import get_all_profiles, get_profile_by_id
from app.services.evidence.recorder import record_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/control-runs", tags=["Control Runs"])


# ─── Database Profiles & Views (Active & Archive DB) ───────────────

@router.get("/database/profiles", response_model=list[DatabaseProfileResponse])
async def list_database_profiles(
    current_user: User = Depends(get_current_user),
):
    """List all available database environments (PostgreSQL, SQLite, MySQL)."""
    return get_all_profiles()

@router.get("/database/source", response_model=DatabaseViewResponse)
async def get_source_database_view(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View live records in the Active Database (source_transactions)."""
    # Ensure database has seed records if empty
    await seed_source_database(db, count=50)

    total = await db.scalar(select(func.count()).select_from(SourceTransaction))
    result = await db.execute(
        select(SourceTransaction).order_by(desc(SourceTransaction.transaction_date)).limit(limit)
    )
    records = result.scalars().all()

    return DatabaseViewResponse(
        table_name="source_transactions (Active Database)",
        total_count=total or 0,
        records=[TransactionRecordResponse.model_validate(r.to_dict()) for r in records],
    )


@router.get("/database/archive", response_model=DatabaseViewResponse)
async def get_archive_database_view(
    run_id: str = Query(None, description="Optional filter by control run ID"),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View live records in the Approved Archive Database (archive_transactions)."""
    query = select(ArchiveTransaction)
    if run_id:
        query = query.where(ArchiveTransaction.control_run_id == run_id)

    total_query = select(func.count()).select_from(ArchiveTransaction)
    if run_id:
        total_query = total_query.where(ArchiveTransaction.control_run_id == run_id)

    total = await db.scalar(total_query)
    result = await db.execute(query.order_by(desc(ArchiveTransaction.archived_at)).limit(limit))
    records = result.scalars().all()

    return DatabaseViewResponse(
        table_name="archive_transactions (Archive Database)",
        total_count=total or 0,
        records=[TransactionRecordResponse.model_validate(r.to_dict()) for r in records],
    )


@router.post("/database/seed")
async def seed_database(
    count: int = Query(50, ge=10, le=200),
    force: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reset / seed synthetic banking records into source_transactions."""
    seeded = await seed_source_database(db, count=count, force=force)
    return {"message": f"Successfully seeded {seeded} records into source_transactions."}


@router.post("/database/clear-all")
async def clear_all_data(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all policies, rules, control runs, records, and approvals, and reseed clean active transactions."""
    import traceback
    try:
        from app.models.policy import Policy, PolicyVersion
        from app.models.rule import PolicyRule, PolicyException
        from app.models.audit import AuditEvidence

        # 1. Delete control runs, approvals, records, and archives
        await db.execute(delete(ApprovalRequest))
        await db.execute(delete(ControlRunRecord))
        await db.execute(delete(ControlRun))
        await db.execute(delete(ArchiveTransaction))

        # 2. Delete policy rules, exceptions, versions, and policies
        await db.execute(delete(PolicyException))
        await db.execute(delete(PolicyRule))
        await db.execute(delete(PolicyVersion))
        await db.execute(delete(Policy))

        # 3. Delete audit evidence
        await db.execute(delete(AuditEvidence))

        # 4. Clean reseed source_transactions
        seeded = await seed_source_database(db, count=50, force=True)
        await db.commit()

        return {
            "message": f"Successfully cleared all rules, runs, policies, and audit evidence. Reseeded {seeded} fresh records in source_transactions."
        }
    except Exception as e:
        logger.error(f"Error in clear_all_data: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))



# ─── Control Runs Lifecycle ─────────────────────────────────────────

@router.post("", status_code=status.HTTP_201_CREATED)
async def start_control_run(
    policy_id: str = Query(..., description="Policy ID to run controls for"),
    database_id: Optional[str] = Query("postgres_core", description="Target database profile ID"),
    num_records: int = Query(50, ge=10, le=200, description="Number of sample records to evaluate"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new control run against a selected database profile — introspects schema, generates dialect SQL, and evaluates."""

    # 1. Get database profile
    db_profile = get_profile_by_id(database_id)
    target_database_name = db_profile["name"]
    target_dialect = db_profile["dialect"]

    # 2. Get policy and latest version
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version.desc())
    )
    version = result.scalars().first()
    if not version or version.analysis_status != "COMPLETED":
        raise HTTPException(status_code=400, detail="Policy must have a completed analysis before running controls")

    # 3. Get rules and exceptions
    rules_result = await db.execute(
        select(PolicyRule)
        .where(PolicyRule.policy_version_id == version.id)
        .order_by(PolicyRule.priority)
    )
    rules = rules_result.scalars().all()

    exc_result = await db.execute(
        select(PolicyException)
        .where(PolicyException.policy_version_id == version.id)
    )
    exceptions = exc_result.scalars().all()

    if not rules:
        raise HTTPException(status_code=400, detail="No rules found for this policy")

    # 4. Ensure live source_transactions are seeded
    await seed_source_database(db, count=max(num_records, 50))

    # 5. Fetch live records from source_transactions (Active DB)
    source_res = await db.execute(
        select(SourceTransaction).limit(num_records)
    )
    source_items = source_res.scalars().all()
    records_to_evaluate = [s.to_dict() for s in source_items]

    # 6. Convert rules/exceptions to dicts
    rules_dicts = [
        {
            "rule_id": r.rule_id,
            "field": r.field,
            "operator": r.operator,
            "value": r.value,
            "unit": r.unit,
            "action": r.action,
            "description": r.description or "",
        }
        for r in rules
    ]
    exc_dicts = [
        {
            "field": e.field,
            "operator": e.operator,
            "value": e.value,
            "action": e.action,
            "description": e.description,
        }
        for e in exceptions
    ]

    # 7. Create control run & Generate SQL Queries for target dialect
    run = ControlRun(
        policy_id=policy_id,
        policy_version_id=version.id,
        status="EVALUATING",
        created_by=current_user.id,
        started_at=datetime.now(timezone.utc),
        target_database=target_database_name,
        database_dialect=target_dialect,
    )
    db.add(run)
    await db.flush()

    sql_queries = await generate_sql_queries(
        rules=rules_dicts,
        exceptions=exc_dicts,
        control_run_id=run.id,
        db=db,
        target_dialect=target_dialect,
    )
    run.generated_sql = sql_queries["selection_sql"]
    run.archival_sql = sql_queries["archival_sql"]
    run.cleanup_sql = sql_queries["cleanup_sql"]

    # 8. Evaluate records against rules
    evaluations = evaluate_records(records_to_evaluate, rules_dicts, exc_dicts)

    # 9. Store results
    eligible_count = 0
    excluded_count = 0
    for eval_result in evaluations:
        rec_data = eval_result["record"]
        txn_id = rec_data.get("transaction_id") or rec_data.get("record_id", "UNKNOWN")
        record = ControlRunRecord(
            control_run_id=run.id,
            record_identifier=txn_id,
            record_data=json.dumps(rec_data),
            matched_rule_id=eval_result["matched_rule_id"],
            is_eligible=eval_result["is_eligible"],
            is_excluded=eval_result["is_excluded"],
            exclusion_reason=eval_result["exclusion_reason"],
        )
        db.add(record)

        if eval_result["is_eligible"]:
            eligible_count += 1
        if eval_result["is_excluded"]:
            excluded_count += 1

    run.total_records = len(evaluations)
    run.eligible_records = eligible_count
    run.excluded_records = excluded_count
    run.status = "EVALUATED"
    await db.commit()

    # Record audit evidence
    await record_event(
        db=db,
        event_type="CONTROL_RUN_STARTED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        policy_id=policy_id,
        policy_version_id=version.id,
        control_run_id=run.id,
        metadata={
            "total_records": len(evaluations),
            "eligible_records": eligible_count,
            "excluded_records": excluded_count,
            "target_database": target_database_name,
            "database_dialect": target_dialect,
            "generated_sql_length": len(run.generated_sql),
        },
    )

    return {
        "run_id": run.id,
        "status": run.status,
        "total_records": run.total_records,
        "eligible_records": eligible_count,
        "excluded_records": excluded_count,
        "target_database": run.target_database,
        "database_dialect": run.database_dialect,
        "generated_sql": run.generated_sql,
        "cleanup_sql": run.cleanup_sql,
        "message": f"Evaluated {run.total_records} records against {target_database_name} ({target_dialect.upper()}). {eligible_count} eligible for archival.",
    }


@router.get("", response_model=ControlRunListResponse)
async def list_control_runs(
    policy_id: str = Query(None, description="Filter by policy ID"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all control runs."""
    query = select(ControlRun).order_by(ControlRun.created_at.desc())
    if policy_id:
        query = query.where(ControlRun.policy_id == policy_id)

    result = await db.execute(query)
    runs = result.scalars().all()

    run_responses = []
    for run in runs:
        policy = await db.get(Policy, run.policy_id)
        resp = ControlRunResponse.model_validate(run)
        resp.policy_name = policy.name if policy else None
        run_responses.append(resp)

    return ControlRunListResponse(runs=run_responses, total=len(run_responses))


@router.get("/{run_id}", response_model=ControlRunDetailResponse)
async def get_control_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get full details of a control run including evaluation results and SQL."""
    run = await db.get(ControlRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Control run not found")

    result = await db.execute(
        select(ControlRunRecord)
        .where(ControlRunRecord.control_run_id == run_id)
        .order_by(ControlRunRecord.is_eligible.desc())
    )
    records = result.scalars().all()

    policy = await db.get(Policy, run.policy_id)
    run_resp = ControlRunResponse.model_validate(run)
    run_resp.policy_name = policy.name if policy else None

    # Get active approval if awaiting or approved
    approval_res = await db.execute(
        select(ApprovalRequest)
        .where(ApprovalRequest.control_run_id == run_id)
        .order_by(ApprovalRequest.created_at.desc())
    )
    approval = approval_res.scalars().first()
    approval_id = approval.id if approval else None

    return ControlRunDetailResponse(
        run=run_resp,
        records=[ControlRunRecordResponse.model_validate(r) for r in records],
        approval_id=approval_id,
    )


# ─── Lifecycle Stage Actions ─────────────────────────────────────────

@router.post("/{run_id}/archive")
async def archive_records(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stage 4→5: Archive eligible records to archive_transactions."""
    run = await db.get(ControlRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Control run not found")
    if run.status not in ("EVALUATED", "EVALUATING", "ARCHIVING"):
        raise HTTPException(status_code=400, detail=f"Cannot archive from status '{run.status}'. Expected 'EVALUATED'.")

    run.status = "ARCHIVING"
    await db.flush()

    archived_count = await archive_eligible_records(db, run_id)

    await record_event(
        db=db,
        event_type="ARCHIVE_COMPLETED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        policy_id=run.policy_id,
        control_run_id=run_id,
        metadata={"archived_records": archived_count, "destination_table": "archive_transactions"},
    )

    return {
        "run_id": run_id,
        "status": "VERIFYING",
        "archived_records": archived_count,
        "message": f"Archived {archived_count} records into archive_transactions. Ready for independent verification.",
    }


@router.post("/{run_id}/verify")
async def verify_records(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stage 5→6: Independently verify archived records in archive_transactions."""
    run = await db.get(ControlRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Control run not found")
    if run.status not in ("VERIFYING", "ARCHIVING"):
        raise HTTPException(status_code=400, detail=f"Cannot verify from status '{run.status}'. Expected 'VERIFYING'.")

    verified_count, issues = await verify_archived_records(db, run_id)

    await record_event(
        db=db,
        event_type="VERIFICATION_COMPLETED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        policy_id=run.policy_id,
        control_run_id=run_id,
        metadata={"verified_records": verified_count, "issues": issues},
    )

    # Auto-create approval request with SQL preview
    approval = ApprovalRequest(
        control_run_id=run_id,
        requested_by=current_user.id,
        requested_by_email=current_user.email,
        records_to_cleanup=verified_count,
        summary=f"Archival verified for {verified_count} records. Review cleanup SQL before applying to source_transactions.",
    )
    db.add(approval)
    await db.commit()

    return {
        "run_id": run_id,
        "status": "AWAITING_APPROVAL",
        "verified_records": verified_count,
        "issues": issues,
        "approval_id": approval.id,
        "message": f"Verification complete. {verified_count} records verified. Approval request created with cleanup SQL preview.",
    }


@router.post("/{run_id}/cleanup")
async def cleanup_records(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stage 8: Execute controlled cleanup SQL query on source_transactions (Active DB)."""
    run = await db.get(ControlRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Control run not found")
    if run.status != "APPROVED":
        raise HTTPException(status_code=400, detail=f"Cannot execute cleanup from status '{run.status}'. Approval required first.")

    run.status = "CLEANING"
    await db.flush()

    cleaned_count = await cleanup_approved_records(db, run_id)

    await record_event(
        db=db,
        event_type="CLEANUP_COMPLETED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        policy_id=run.policy_id,
        control_run_id=run_id,
        metadata={"cleaned_records": cleaned_count, "target_table": "source_transactions"},
    )

    return {
        "run_id": run_id,
        "status": "FINAL_VERIFICATION",
        "cleaned_records": cleaned_count,
        "message": f"Cleanup executed successfully: {cleaned_count} records deleted from Active DB (source_transactions). Ready for final verification.",
    }


@router.post("/{run_id}/final-verify")
async def final_verify(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stage 9: Final verification — confirms zero source remnants and complete archive presence."""
    run = await db.get(ControlRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Control run not found")
    if run.status != "FINAL_VERIFICATION":
        raise HTTPException(status_code=400, detail=f"Cannot final-verify from status '{run.status}'. Expected 'FINAL_VERIFICATION'.")

    verified_count, issues = await final_verify_cleanup(db, run_id)

    await record_event(
        db=db,
        event_type="FINAL_VERIFICATION_COMPLETED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        policy_id=run.policy_id,
        control_run_id=run_id,
        metadata={"final_verified_records": verified_count, "issues": issues},
    )

    return {
        "run_id": run_id,
        "status": "COMPLETED",
        "final_verified_records": verified_count,
        "issues": issues,
        "message": f"Final reconciliation complete. {verified_count} records verified intact in Archive DB and removed from Active DB.",
    }

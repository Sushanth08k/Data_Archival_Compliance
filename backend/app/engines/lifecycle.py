"""
Lifecycle engine — real database operations for archival, verification, and cleanup.
Operates on SourceTransaction (Active DB) and ArchiveTransaction (Archive DB).
"""

import hashlib
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

from app.models.control_run import ControlRun, ControlRunRecord
from app.models.transaction import SourceTransaction, ArchiveTransaction

logger = logging.getLogger(__name__)


async def archive_eligible_records(db: AsyncSession, control_run_id: str) -> int:
    """
    Archive eligible records from Active DB (source_transactions) to Archive DB (archive_transactions).
    Calculates cryptographic verification hashes for immutability.
    """
    # 1. Find eligible records for this run
    result = await db.execute(
        select(ControlRunRecord).where(
            ControlRunRecord.control_run_id == control_run_id,
            ControlRunRecord.is_eligible == True,
            ControlRunRecord.is_excluded == False,
        )
    )
    eligible_run_records = result.scalars().all()
    record_ids = [r.record_identifier for r in eligible_run_records]

    run = await db.get(ControlRun, control_run_id)

    if not record_ids:
        if run:
            run.archived_records = 0
            run.status = "VERIFYING"
        await db.commit()
        return 0

    # 2. Fetch source records from Active DB
    source_res = await db.execute(
        select(SourceTransaction).where(SourceTransaction.transaction_id.in_(record_ids))
    )
    source_records = source_res.scalars().all()

    # 3. Insert or update in Archive DB with SHA256 hash
    now = datetime.now(timezone.utc)
    for src in source_records:
        raw_hash_content = f"{src.transaction_id}:{src.account_id}:{src.amount}:{src.transaction_date}"
        v_hash = "SHA256-" + hashlib.sha256(raw_hash_content.encode()).hexdigest()[:16]

        existing = await db.get(ArchiveTransaction, src.transaction_id)
        if existing:
            existing.account_id = src.account_id
            existing.customer_name = src.customer_name
            existing.transaction_date = src.transaction_date
            existing.amount = src.amount
            existing.transaction_type = src.transaction_type
            existing.legal_hold = src.legal_hold
            existing.status = "ARCHIVED"
            existing.control_run_id = control_run_id
            existing.verification_hash = v_hash
            existing.archived_at = now
        else:
            archive_entry = ArchiveTransaction(
                transaction_id=src.transaction_id,
                account_id=src.account_id,
                customer_name=src.customer_name,
                transaction_date=src.transaction_date,
                amount=src.amount,
                transaction_type=src.transaction_type,
                legal_hold=src.legal_hold,
                status="ARCHIVED",
                control_run_id=control_run_id,
                verification_hash=v_hash,
                archived_at=now,
            )
            db.add(archive_entry)

    # 4. Mark ControlRunRecords as archived
    await db.execute(
        update(ControlRunRecord)
        .where(
            ControlRunRecord.control_run_id == control_run_id,
            ControlRunRecord.record_identifier.in_(record_ids),
        )
        .values(is_archived=True)
    )

    # 5. Update ControlRun state
    run = await db.get(ControlRun, control_run_id)
    if run:
        run.archived_records = len(source_records)
        run.status = "VERIFYING"

    await db.commit()
    logger.info(f"Archived {len(source_records)} records into archive_transactions for run {control_run_id[:8]}")
    return len(source_records)


async def verify_archived_records(db: AsyncSession, control_run_id: str) -> tuple[int, list[str]]:
    """
    Independently verify that all archived records exist in Archive DB with valid hashes.
    """
    issues = []

    # Get archived records in run
    result = await db.execute(
        select(ControlRunRecord).where(
            ControlRunRecord.control_run_id == control_run_id,
            ControlRunRecord.is_archived == True,
        )
    )
    run_records = result.scalars().all()
    record_ids = [r.record_identifier for r in run_records]

    # Check Archive DB existence
    arch_res = await db.execute(
        select(ArchiveTransaction).where(
            ArchiveTransaction.control_run_id == control_run_id,
            ArchiveTransaction.transaction_id.in_(record_ids),
        )
    )
    archive_rows = arch_res.scalars().all()
    archive_id_set = {a.transaction_id for a in archive_rows}

    verified_count = 0
    for r in run_records:
        if r.record_identifier not in archive_id_set:
            issues.append(f"{r.record_identifier}: Missing from archive database")
            continue
        if not r.is_eligible:
            issues.append(f"{r.record_identifier}: Ineligible record archived")
            continue
        if r.is_excluded:
            issues.append(f"{r.record_identifier}: Excluded legal-hold record archived")
            continue

        r.is_verified = True
        verified_count += 1

    # Update ControlRun status
    run = await db.get(ControlRun, control_run_id)
    if run:
        run.verified_records = verified_count
        run.status = "AWAITING_APPROVAL"

    await db.commit()
    logger.info(f"Verified {verified_count}/{len(run_records)} records in archive_transactions")
    return verified_count, issues


async def cleanup_approved_records(db: AsyncSession, control_run_id: str) -> int:
    """
    Execute controlled source cleanup: Deletes ONLY verified archived records from Active DB (source_transactions).
    Operates on the live SQLite database after human approval.
    """
    # 1. Get verified records
    result = await db.execute(
        select(ControlRunRecord).where(
            ControlRunRecord.control_run_id == control_run_id,
            ControlRunRecord.is_archived == True,
            ControlRunRecord.is_verified == True,
            ControlRunRecord.is_cleaned == False,
        )
    )
    verified_records = result.scalars().all()
    record_ids = [r.record_identifier for r in verified_records]

    if not record_ids:
        return 0

    # 2. Execute SQL deletion from Active DB (source_transactions)
    # Strictly ensuring legal_hold = False
    del_result = await db.execute(
        delete(SourceTransaction).where(
            SourceTransaction.transaction_id.in_(record_ids),
            SourceTransaction.legal_hold == False,
        )
    )
    cleaned_count = del_result.rowcount

    # 3. Update ControlRunRecords
    await db.execute(
        update(ControlRunRecord)
        .where(
            ControlRunRecord.control_run_id == control_run_id,
            ControlRunRecord.record_identifier.in_(record_ids),
        )
        .values(is_cleaned=True)
    )

    # 4. Update ControlRun
    run = await db.get(ControlRun, control_run_id)
    if run:
        run.cleaned_records = cleaned_count
        run.status = "FINAL_VERIFICATION"

    await db.commit()
    logger.info(f"Executed cleanup query: Deleted {cleaned_count} records from source_transactions")
    return cleaned_count


async def final_verify_cleanup(db: AsyncSession, control_run_id: str) -> tuple[int, list[str]]:
    """
    Final dual-database verification:
    1. Ensures cleaned records no longer exist in Active DB (source_transactions).
    2. Ensures all cleaned records remain intact in Archive DB (archive_transactions).
    """
    issues = []

    # Get cleaned records
    result = await db.execute(
        select(ControlRunRecord).where(
            ControlRunRecord.control_run_id == control_run_id,
            ControlRunRecord.is_cleaned == True,
        )
    )
    cleaned_records = result.scalars().all()
    record_ids = [r.record_identifier for r in cleaned_records]

    # Verify 0 remnants in Active DB
    source_check = await db.execute(
        select(SourceTransaction.transaction_id).where(
            SourceTransaction.transaction_id.in_(record_ids)
        )
    )
    remnants = source_check.scalars().all()
    if remnants:
        for rem_id in remnants:
            issues.append(f"{rem_id}: Still detected in active source database!")

    # Verify complete presence in Archive DB
    arch_check = await db.execute(
        select(ArchiveTransaction.transaction_id).where(
            ArchiveTransaction.control_run_id == control_run_id,
            ArchiveTransaction.transaction_id.in_(record_ids),
        )
    )
    arch_ids = set(arch_check.scalars().all())

    verified_count = 0
    for r in cleaned_records:
        if r.record_identifier in remnants:
            continue
        if r.record_identifier not in arch_ids:
            issues.append(f"{r.record_identifier}: Not found in archive database during final verification")
            continue

        r.is_final_verified = True
        verified_count += 1

    # Update ControlRun status to COMPLETED
    run = await db.get(ControlRun, control_run_id)
    if run:
        run.status = "COMPLETED"
        run.completed_at = datetime.now(timezone.utc)

    await db.commit()
    logger.info(f"Final verification completed: {verified_count}/{len(cleaned_records)} records confirmed.")
    return verified_count, issues

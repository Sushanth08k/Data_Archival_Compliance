"""
Synthetic Database Seeder — seeds realistic banking transactions into the Active Database.
Ensures zero unique constraint collisions and resets cleanly when force=True.
"""

import random
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete

from app.models.transaction import SourceTransaction

COMPANIES = [
    "Acme Corp", "GlobalTech Inc", "Summit Healthcare", "Vertex Logistics",
    "Pioneer Energy", "Nexus Financial", "Atlas Trading Co", "Meridian Media",
    "Quantum Systems", "Horizon Ventures", "Sterling Capital", "Pacific Rim Corp",
    "Northern Trust Group", "Eagle Industrial", "Cascade Robotics", "Delta Aviation",
    "Pinnacle Retail", "Orion BioTech", "Silverline Maritime", "Beacon Infrastructure",
]

TRANSACTION_TYPES = ["WIRE", "ACH", "DEBIT", "CREDIT"]


async def seed_source_database(db: AsyncSession, count: int = 50, force: bool = False) -> int:
    """
    Seed realistic banking records into source_transactions.
    If force=True, cleanly resets source_transactions to fresh demo records.
    If force=False, only seeds if existing count is below 30.
    """
    existing_count = await db.scalar(select(func.count()).select_from(SourceTransaction)) or 0

    if force:
        # Cleanly reset active table
        await db.execute(delete(SourceTransaction))
        await db.flush()
        existing_ids = set()
    else:
        # Only auto-seed if the active database is completely empty (0 records)
        if existing_count > 0:
            return existing_count
        existing_ids = set()

    now = datetime.now(timezone.utc)
    base_counter = 100000 + random.randint(1000, 90000) if not force else 100000
    added = 0

    for i in range(count):
        cand_id = f"TXN-{base_counter + i}"
        while cand_id in existing_ids:
            cand_id = f"TXN-{random.randint(100000, 999999)}"
        existing_ids.add(cand_id)

        acc_id = f"ACC-{random.randint(1000, 9999)}"
        company = random.choice(COMPANIES)
        
        # 65% older than 5 years (1850 - 3200 days ago) — guaranteed to be eligible for retention archival
        # 35% newer (100 - 1600 days ago)
        if random.random() < 0.65:
            days_ago = random.randint(1850, 3200)
        else:
            days_ago = random.randint(100, 1600)

        txn_date = (now - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        amount = round(random.uniform(500.0, 95000.0), 2)
        txn_type = random.choice(TRANSACTION_TYPES)
        
        # ~10% have active legal hold
        has_legal_hold = (random.random() < 0.10)

        # Set created_at to align with the historical transaction_date
        created_dt = datetime.strptime(txn_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        record = SourceTransaction(
            transaction_id=cand_id,
            account_id=acc_id,
            customer_name=company,
            transaction_date=txn_date,
            amount=amount,
            transaction_type=txn_type,
            legal_hold=has_legal_hold,
            status="COMPLETED",
            created_at=created_dt,
        )
        db.add(record)
        added += 1

    await db.commit()
    return added

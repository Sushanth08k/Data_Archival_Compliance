"""
Rule engine — evaluates policy rules against records.
Generates sample data and determines eligibility for archival.
"""

import json
import random
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Sample data templates for generating realistic test records
SAMPLE_NAMES = [
    "Acme Corp", "GlobalTech Inc", "Summit LLC", "Vertex Partners",
    "Pioneer Holdings", "Nexus Financial", "Atlas Trading", "Meridian Group",
    "Quantum Systems", "Horizon Ventures", "Sterling Capital", "Pacific Rim Co",
    "Northern Trust", "Eagle Industries", "Cascade Solutions", "Delta Finance",
    "Pinnacle Corp", "Orion Labs", "Silverline Inc", "Beacon Analytics",
]

ACCOUNT_TYPES = ["checking", "savings", "investment", "retirement", "trust", "brokerage"]
STATUSES = ["active", "inactive", "dormant", "closed"]


def generate_sample_records(num_records: int = 50) -> list[dict[str, Any]]:
    """
    Generate realistic sample transaction/account records for rule evaluation.
    These simulate records that might exist in a real compliance database.
    """
    records = []
    now = datetime.now(timezone.utc)

    for i in range(num_records):
        # Random date between 1 and 10 years ago
        days_ago = random.randint(30, 3650)
        transaction_date = now - timedelta(days=days_ago)

        # Some records have legal holds
        has_legal_hold = random.random() < 0.1  # 10% chance

        # Some records are regulatory flagged
        is_regulatory = random.random() < 0.08  # 8% chance

        # Account balance
        balance = round(random.uniform(100, 500000), 2)

        record = {
            "record_id": f"REC-{i+1:04d}",
            "account_name": random.choice(SAMPLE_NAMES),
            "account_type": random.choice(ACCOUNT_TYPES),
            "account_status": random.choice(STATUSES),
            "transaction_date": transaction_date.isoformat(),
            "transaction_amount": round(random.uniform(10, 100000), 2),
            "balance": balance,
            "legal_hold": has_legal_hold,
            "regulatory_flag": is_regulatory,
            "last_activity_date": (now - timedelta(days=random.randint(1, days_ago))).isoformat(),
            "created_date": (transaction_date - timedelta(days=random.randint(0, 365))).isoformat(),
            "retention_category": random.choice(["standard", "extended", "permanent"]),
        }
        records.append(record)

    return records


def _parse_datetime(val: Any) -> datetime | None:
    """Safely parse various date/datetime representations into UTC timezone-aware datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    if hasattr(val, "year") and hasattr(val, "month") and hasattr(val, "day") and not hasattr(val, "hour"):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            s = val.strip().replace("Z", "+00:00")
            if "T" not in s and " " not in s and len(s) == 10:
                s += "T00:00:00+00:00"
            dt = datetime.fromisoformat(s)
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except Exception:
            return None
    return None


def evaluate_rule(record: dict, rule: dict) -> bool:
    """
    Evaluate a single rule against a single record.
    Returns True if the record matches the rule condition.
    """
    field = rule.get("field", "")
    operator = rule.get("operator", "")
    value = rule.get("value", "")
    unit = rule.get("unit")

    # 1. Schema Entity Scoping:
    # A rule that specifically targets an entity category (e.g. "audit logs", "support tickets", "employee records")
    # must ONLY evaluate against records from that schema or containing those entity attributes.
    # It must NEVER misapply an audit log rule to financial banking transactions.
    desc = (rule.get("description") or "").lower()
    record_keys = {str(k).lower() for k in record.keys()}
    is_financial_transaction = any(k in record_keys for k in ("transaction_id", "transaction_date", "account_id", "amount"))

    if is_financial_transaction:
        if any(term in desc for term in ("audit log", "system log", "security investigation log", "logs older than")):
            if not any(k in record_keys for k in ("log_id", "log_type", "audit_log", "event_type")):
                return False
        if any(term in desc for term in ("support ticket", "ticket closure", "customer support record")):
            if not any(k in record_keys for k in ("ticket_id", "closure_date", "complaint")):
                return False
        if any(term in desc for term in ("employee record", "employment dispute", "termination date")):
            if not any(k in record_keys for k in ("employee_id", "termination_date")):
                return False
        if any(term in desc for term in ("customer document", "documents older than")):
            if not any(k in record_keys for k in ("document_id", "document_type", "file_path")):
                return False

    # Get the record field value
    record_value = record.get(field)

    # Intelligent banking date fallback:
    # If the policy rule targets created_at, created_date, or a date field,
    # but the record has a distinct business transaction_date:
    if field in ("created_at", "created_date", "document_created_at", "closed_date", "date"):
        txn_date = record.get("transaction_date")
        if txn_date:
            if record_value is None:
                record_value = txn_date
            else:
                rec_dt = _parse_datetime(record_value)
                txn_dt = _parse_datetime(txn_date)
                if rec_dt and txn_dt:
                    now_utc = datetime.now(timezone.utc)
                    # If record_value is today's insertion timestamp while txn_date is the real historical date
                    if (now_utc - rec_dt).days < 2 and (now_utc - txn_dt).days >= 2:
                        record_value = txn_date

    if record_value is None:
        return False

    try:
        if operator == "OLDER_THAN":
            # Date comparison — check if the record date is older than the threshold
            threshold_days = _to_days(float(value), unit)
            record_date = _parse_datetime(record_value)
            if not record_date:
                return False
            cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
            return record_date < cutoff

        elif operator == "NEWER_THAN":
            threshold_days = _to_days(float(value), unit)
            record_date = _parse_datetime(record_value)
            if not record_date:
                return False
            cutoff = datetime.now(timezone.utc) - timedelta(days=threshold_days)
            return record_date > cutoff

        elif operator == "EQUALS":
            val_str = str(value).lower()
            rec_str = str(record_value).lower()
            if val_str in ("true", "1") and rec_str in ("true", "1"):
                return True
            if val_str in ("false", "0") and rec_str in ("false", "0"):
                return True
            return rec_str == val_str

        elif operator == "NOT_EQUALS":
            val_str = str(value).lower()
            rec_str = str(record_value).lower()
            if val_str in ("true", "1") and rec_str in ("true", "1"):
                return False
            if val_str in ("false", "0") and rec_str in ("false", "0"):
                return False
            return rec_str != val_str

        elif operator == "GREATER_THAN":
            return float(record_value) > float(value)

        elif operator == "LESS_THAN":
            return float(record_value) < float(value)

    except (ValueError, TypeError) as e:
        logger.warning(f"Rule evaluation error for field={field}: {e}")
        return False

    return False


def evaluate_exception(record: dict, exception: dict) -> tuple[bool, str]:
    """
    Check if a record matches an exception condition.
    Returns (matches, reason).
    """
    field = exception.get("field", "")
    operator = exception.get("operator", "")
    value = exception.get("value", "")
    reason = exception.get("description", "Excluded by exception")

    record_value = record.get(field)
    if record_value is None:
        return False, ""

    if operator == "EQUALS":
        val_str = str(value).lower()
        rec_str = str(record_value).lower()
        if val_str in ("true", "1") and rec_str in ("true", "1"):
            matches = True
        elif val_str in ("false", "0") and rec_str in ("false", "0"):
            matches = True
        else:
            matches = (rec_str == val_str)
    elif operator == "NOT_EQUALS":
        val_str = str(value).lower()
        rec_str = str(record_value).lower()
        if val_str in ("true", "1") and rec_str in ("true", "1"):
            matches = False
        elif val_str in ("false", "0") and rec_str in ("false", "0"):
            matches = False
        else:
            matches = (rec_str != val_str)
    else:
        matches = False

    return matches, reason if matches else ""


def evaluate_records(
    records: list[dict],
    rules: list[dict],
    exceptions: list[dict],
) -> list[dict[str, Any]]:
    """
    Evaluate all records against all rules and exceptions.
    Returns a list of evaluation results.
    """
    results = []

    for record in records:
        result = {
            "record": record,
            "record_identifier": record.get("record_id", str(uuid.uuid4())[:8]),
            "is_eligible": False,
            "is_excluded": False,
            "matched_rule_id": None,
            "exclusion_reason": None,
        }

        # Check exceptions first — excluded records skip rule evaluation
        for exc in exceptions:
            matches, reason = evaluate_exception(record, exc)
            if matches:
                result["is_excluded"] = True
                result["exclusion_reason"] = reason
                break

        if not result["is_excluded"]:
            # Evaluate rules
            for rule in rules:
                if rule.get("action") in ("ARCHIVE", "DELETE"):
                    if evaluate_rule(record, rule):
                        result["is_eligible"] = True
                        result["matched_rule_id"] = rule.get("rule_id", "UNKNOWN")
                        break

        results.append(result)

    return results


def _to_days(value: float, unit: str | None) -> float:
    """Convert a value+unit to days."""
    if unit is None:
        return value
    unit = unit.lower()
    if unit == "years":
        return value * 365.25
    elif unit == "months":
        return value * 30.44
    elif unit == "days":
        return value
    elif unit == "weeks":
        return value * 7
    return value

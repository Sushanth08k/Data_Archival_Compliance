"""
Policy analysis service — orchestrates policy rule extraction.
Uses regex/heuristic extraction engine by default, or an external LLM
if configured, with seamless fallback.
"""

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.models.policy import Policy, PolicyVersion
from app.models.rule import PolicyRule, PolicyException
from app.services.llm.factory import get_llm_service
from app.services.policies.regex_extractor import extract_policy_with_regex
from app.services.evidence.recorder import record_event

logger = logging.getLogger(__name__)

ANALYSIS_SYSTEM_PROMPT = """You are a compliance policy analysis engine. 
Your job is to read policy documents and extract structured, machine-executable rules.

You must ALWAYS respond with valid JSON matching this exact schema:
{
  "policy_name": "string — name of the policy",
  "scope": "string — what data/systems this policy applies to",
  "description": "string — brief summary of the policy",
  "requirements": [
    {
      "requirement_id": "REQ-001",
      "description": "string — what the policy requires"
    }
  ],
  "rules": [
    {
      "rule_id": "RULE-001",
      "description": "string — human-readable description of the rule",
      "rule_type": "RETENTION | ARCHIVAL | VERIFICATION",
      "condition": {
        "field": "string — the database field name (e.g. transaction_date, legal_hold)",
        "operator": "OLDER_THAN | NEWER_THAN | EQUALS | NOT_EQUALS | GREATER_THAN | LESS_THAN",
        "value": "string or number — the threshold value",
        "unit": "years | months | days | null — time unit if applicable"
      },
      "action": "ARCHIVE | DELETE | VERIFY | EXCLUDE"
    }
  ],
  "exceptions": [
    {
      "field": "string — field to check",
      "operator": "EQUALS | NOT_EQUALS",
      "value": "string or boolean — the value to match",
      "action": "EXCLUDE",
      "reason": "string — why this exception exists"
    }
  ],
  "ambiguities": [
    {
      "type": "MISSING_SOURCE | MISSING_FIELD | MISSING_THRESHOLD | UNCLEAR_SCOPE | MISSING_ARCHIVE_DESTINATION",
      "severity": "HIGH | MEDIUM | LOW",
      "description": "string — what is ambiguous or missing",
      "requires_human_review": true
    }
  ],
  "source_references": [
    "string — relevant quotes from the document"
  ]
}
"""


async def analyze_policy_text(
    db: AsyncSession,
    policy_version_id: str,
    extracted_text: str,
    actor_id: str = None,
    actor_email: str = None,
) -> dict[str, Any]:
    """
    Extract structured policy rules and exceptions.
    Uses regex extractor or configured LLM service.
    Persists rules, exceptions, and audit records into the database.
    """
    result = await db.execute(
        select(PolicyVersion).where(PolicyVersion.id == policy_version_id)
    )
    version = result.scalar_one_or_none()
    if not version:
        raise ValueError(f"PolicyVersion {policy_version_id} not found")

    version.analysis_status = "ANALYZING"
    await db.flush()

    prompt = f"""Analyze the following policy document and extract all structured rules, exceptions, and ambiguities.

--- POLICY DOCUMENT START ---
{extracted_text}
--- POLICY DOCUMENT END ---

Return your analysis as a single JSON object matching the required schema."""

    analysis: dict[str, Any] | None = None
    try:
        llm = get_llm_service()
        analysis = await llm.generate_structured(
            prompt=prompt,
            system_instruction=ANALYSIS_SYSTEM_PROMPT,
        )
    except Exception as e:
        logger.warning(f"Configured LLM service failed ({e}). Falling back to Regex extraction engine.")
        try:
            analysis = extract_policy_with_regex(extracted_text)
        except Exception as rex_err:
            version.analysis_status = "FAILED"
            version.analysis_result = json.dumps({"error": f"Regex extraction failed: {rex_err}"})
            await db.flush()
            logger.error(f"Regex extraction also failed for version {policy_version_id}: {rex_err}")
            raise

    # Store the raw analysis result
    version.analysis_result = json.dumps(analysis)
    version.analysis_status = "COMPLETED"

    # Safely update parent Policy
    policy = await db.get(Policy, version.policy_id)
    if policy:
        if analysis.get("policy_name"):
            policy.name = analysis["policy_name"]
        if analysis.get("scope"):
            policy.scope = analysis["scope"]
        if analysis.get("description"):
            policy.description = analysis["description"]
        policy.status = "ACTIVE"

    # Clean up any existing rules/exceptions for this version (in case of re-analysis)
    await db.execute(
        delete(PolicyRule).where(PolicyRule.policy_version_id == policy_version_id)
    )
    await db.execute(
        delete(PolicyException).where(PolicyException.policy_version_id == policy_version_id)
    )

    # Create PolicyRule records
    rules_data = analysis.get("rules", [])
    for i, rule_data in enumerate(rules_data):
        condition = rule_data.get("condition", {})
        rule = PolicyRule(
            policy_version_id=policy_version_id,
            rule_id=rule_data.get("rule_id", f"RULE-{i+1:03d}"),
            rule_type=rule_data.get("rule_type", "RETENTION"),
            description=rule_data.get("description", ""),
            field=condition.get("field", "unknown"),
            operator=condition.get("operator", "EQUALS"),
            value=str(condition.get("value", "")),
            unit=condition.get("unit"),
            action=rule_data.get("action", "ARCHIVE"),
            priority=i,
            is_valid=True,
        )
        db.add(rule)

    # Create PolicyException records
    exceptions_data = analysis.get("exceptions", [])
    for exc_data in exceptions_data:
        exc = PolicyException(
            policy_version_id=policy_version_id,
            field=exc_data.get("field", "unknown"),
            operator=exc_data.get("operator", "EQUALS"),
            value=str(exc_data.get("value", "")),
            action=exc_data.get("action", "EXCLUDE"),
            description=exc_data.get("reason", ""),
        )
        db.add(exc)

    await db.flush()

    # Record audit evidence
    await record_event(
        db=db,
        event_type="POLICY_ANALYZED",
        actor_id=actor_id,
        actor_email=actor_email,
        policy_id=version.policy_id,
        policy_version_id=policy_version_id,
        metadata={
            "rules_count": len(rules_data),
            "exceptions_count": len(exceptions_data),
            "ambiguities_count": len(analysis.get("ambiguities", [])),
            "extractor": "regex",
        },
    )

    return analysis

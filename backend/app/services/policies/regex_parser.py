"""
Regex-based policy parser — extracts structured rules, exceptions, and metadata
from policy documents using pattern matching.

This serves as a fallback when the LLM API is unavailable, and also works
as the primary parser for well-structured policy documents.
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ─── Word-to-number mapping ────────────────────────────────────

WORD_TO_NUM = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
}

# ─── Time period patterns ──────────────────────────────────────

TIME_PERIOD_RE = re.compile(
    r'(?:(?:older|more)\s+than\s+)?'
    r'(?:(?:at\s+least|a\s+minimum\s+of|minimum)\s+)?'
    r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|'
    r'eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty)\s+'
    r'(years?|months?|days?|weeks?)',
    re.IGNORECASE,
)

# ─── Operation mapping ─────────────────────────────────────────

OPERATION_MAP = {
    "ARCHIVE": "ARCHIVE",
    "ARCHIVED": "ARCHIVE",
    "ARCHIVAL": "ARCHIVE",
    "DELETE": "DELETE",
    "REMOVE": "DELETE",
    "REMOVED": "DELETE",
    "REMOVAL": "DELETE",
    "EXCLUDE": "EXCLUDE",
    "EXCLUDED": "EXCLUDE",
    "VERIFY": "VERIFY",
    "VERIFIED": "VERIFY",
    "VERIFICATION": "VERIFY",
    "RETAIN": "ARCHIVE",  # Retention maps to archive action
    "RETAINED": "ARCHIVE",
    "RETENTION": "ARCHIVE",
    "REVIEW": "VERIFY",
    "REVIEWED": "VERIFY",
}

# ─── Condition patterns ────────────────────────────────────────

CONDITION_EQUALS_RE = re.compile(
    r'(\w+(?:_\w+)*)\s+equals?\s+(.+?)(?:\.|$)',
    re.IGNORECASE | re.MULTILINE,
)

FIELD_OLDER_THAN_RE = re.compile(
    r'(\w+(?:_\w+)*)\s+(?:is\s+)?older\s+than',
    re.IGNORECASE,
)

FIELD_CLOSED_RE = re.compile(
    r'(?:closed|inactive)\s+(?:for\s+)?(?:more\s+than\s+)?'
    r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|'
    r'eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty)\s+'
    r'(years?|months?|days?)',
    re.IGNORECASE,
)


def _parse_number(s: str) -> float:
    """Convert a string number (digit or word) to float."""
    s = s.strip().lower()
    if s in WORD_TO_NUM:
        return float(WORD_TO_NUM[s])
    try:
        return float(s)
    except ValueError:
        return 0


def _normalize_unit(unit: str) -> str:
    """Normalize unit to plural form."""
    unit = unit.lower().rstrip("s")
    return unit + "s"  # years, months, days, weeks


def _extract_operation(text: str) -> str | None:
    """Extract operation type from text like 'Operation: ARCHIVE'."""
    match = re.search(r'Operation:\s*(\w+)', text, re.IGNORECASE)
    if match:
        op = match.group(1).upper()
        return OPERATION_MAP.get(op, op)
    return None


def _extract_policy_sections(text: str) -> list[dict[str, str]]:
    """
    Split a document into individual policy sections.
    Looks for headers like:
      ============================================================
      POLICY 1: CUSTOMER TRANSACTION DATA ARCHIVAL
      ============================================================
    """
    # Split by policy section headers
    pattern = re.compile(
        r'={3,}\s*\n\s*POLICY\s+\d+\s*:\s*(.+?)\s*\n\s*={3,}',
        re.IGNORECASE,
    )

    splits = pattern.split(text)

    sections = []
    if len(splits) >= 3:
        # splits = [preamble, title1, body1, title2, body2, ...]
        for i in range(1, len(splits), 2):
            title = splits[i].strip()
            body = splits[i + 1] if i + 1 < len(splits) else ""
            sections.append({"title": title, "body": body})

    if not sections:
        # No policy sections found — treat entire text as one policy
        sections.append({"title": "", "body": text})

    return sections


def _extract_global_requirements(text: str) -> list[dict[str, str]]:
    """Extract global compliance requirements from the document."""
    requirements = []

    # Find the global requirements section
    global_match = re.search(
        r'GLOBAL\s+COMPLIANCE\s+REQUIREMENTS\s*={0,}\s*\n(.*?)(?:END\s+OF|$)',
        text, re.IGNORECASE | re.DOTALL,
    )
    if not global_match:
        return requirements

    section = global_match.group(1)

    # Extract numbered items
    items = re.findall(
        r'(\d+)\.\s+(.+?)(?=\n\s*\d+\.|$)',
        section, re.DOTALL,
    )

    for num, desc in items:
        desc = re.sub(r'\s+', ' ', desc).strip().rstrip('.')
        requirements.append({
            "requirement_id": f"GLOBAL-{num.zfill(3)}",
            "description": desc,
        })

    return requirements


def _parse_policy_section(title: str, body: str, policy_index: int) -> dict[str, Any]:
    """
    Parse a single policy section into structured rules and exceptions.
    Returns a dict with rules, exceptions, and metadata for this policy.
    """
    policy = {
        "policy_id": "",
        "policy_name": title,
        "scope": "",
        "description": "",
        "source_system": "",
        "source_table": "",
        "date_field": "",
        "rules": [],
        "exceptions": [],
        "constraints": [],
    }

    # Extract Policy ID
    pid_match = re.search(r'Policy\s+ID:\s*(\S+)', body, re.IGNORECASE)
    if pid_match:
        policy["policy_id"] = pid_match.group(1)

    # Extract source info
    src_match = re.search(r'Source\s+system:\s*(.+?)\.?\s*$', body, re.IGNORECASE | re.MULTILINE)
    if src_match:
        policy["source_system"] = src_match.group(1).strip()

    table_match = re.search(r'Source\s+table:\s*(\w+)', body, re.IGNORECASE)
    if table_match:
        policy["source_table"] = table_match.group(1).strip()

    # Extract date field (matches patterns like "Transaction date field: transaction_date")
    date_field_match = re.search(
        r'(?:date|closure|creation|created)\s+field:\s*(\w+)',
        body, re.IGNORECASE,
    )
    if date_field_match:
        policy["date_field"] = date_field_match.group(1).strip()

    # Extract description — first paragraph(s) before "Rules:" or "Source system:"
    desc_match = re.search(
        r'^(.*?)(?=\s*(?:Source\s+system|Rules:|Rule\s+\d+))',
        body, re.IGNORECASE | re.DOTALL,
    )
    if desc_match:
        desc_text = desc_match.group(1).strip()
        # Remove the Policy ID line
        desc_text = re.sub(r'Policy\s+ID:\s*\S+\s*', '', desc_text).strip()
        desc_text = re.sub(r'\s+', ' ', desc_text).strip()
        policy["description"] = desc_text

    if not policy["scope"]:
        policy["scope"] = f"{policy['source_system']} / {policy['source_table']}" if policy["source_system"] else ""

    # ─── Extract Rules ──────────────────────────────────────────

    # Split body into rule blocks
    rule_blocks = re.split(r'\n\s*Rule\s+(\d+)\s*:', body, flags=re.IGNORECASE)

    # rule_blocks = [preamble, num1, block1, num2, block2, ...]
    if len(rule_blocks) >= 3:
        for i in range(1, len(rule_blocks), 2):
            rule_num = rule_blocks[i]
            block = rule_blocks[i + 1] if i + 1 < len(rule_blocks) else ""

            # Stop if we hit "Constraints:"
            constraint_split = re.split(r'\n\s*Constraints:', block, maxsplit=1, flags=re.IGNORECASE)
            rule_text = constraint_split[0]
            if len(constraint_split) > 1:
                _parse_constraints(constraint_split[1], policy)

            operation = _extract_operation(rule_text)
            if not operation:
                # Try to infer from text
                if re.search(r'must\s+(?:be\s+)?archived|must\s+be\s+(?:moved|transferred)\s+to', rule_text, re.IGNORECASE):
                    operation = "ARCHIVE"
                elif re.search(r'must\s+not\s+be\s+(?:archived|removed)', rule_text, re.IGNORECASE):
                    operation = "EXCLUDE"
                elif re.search(r'must\s+(?:be\s+)?verif|must\s+(?:be\s+)?review|before\s+(?:any\s+)?(?:source\s+)?(?:record\s+)?removal', rule_text, re.IGNORECASE):
                    operation = "VERIFY"
                elif re.search(r'must\s+(?:be\s+)?retain', rule_text, re.IGNORECASE):
                    operation = "ARCHIVE"

            # Build the description
            desc = re.sub(r'Operation:\s*\w+\.?\s*', '', rule_text).strip()
            desc = re.sub(r'Condition:\s*', '', desc)
            desc = re.sub(r'\s+', ' ', desc).strip().rstrip('.')

            prefix = policy["policy_id"] or f"POL-{policy_index+1:03d}"
            rule_id = f"{prefix}-RULE-{rule_num.zfill(3)}"

            # Determine condition
            condition = _extract_condition(rule_text, policy)

            if operation == "EXCLUDE":
                # This is an exception, not a rule
                exc = {
                    "field": condition.get("field", "unknown"),
                    "operator": condition.get("operator", "EQUALS"),
                    "value": str(condition.get("value", "")),
                    "action": "EXCLUDE",
                    "reason": desc,
                }
                policy["exceptions"].append(exc)
            else:
                rule = {
                    "rule_id": rule_id,
                    "description": desc,
                    "rule_type": _infer_rule_type(operation),
                    "condition": condition,
                    "action": operation or "ARCHIVE",
                }
                policy["rules"].append(rule)

    # ─── Extract constraints ────────────────────────────────────

    constraint_match = re.search(
        r'Constraints:\s*\n((?:\s*-\s+.+\n?)+)',
        body, re.IGNORECASE,
    )
    if constraint_match:
        _parse_constraints(constraint_match.group(1), policy)

    return policy


def _extract_condition(text: str, policy: dict) -> dict[str, Any]:
    """
    Extract the condition (field, operator, value, unit) from rule text.
    """
    condition = {
        "field": policy.get("date_field", "unknown"),
        "operator": "OLDER_THAN",
        "value": "",
        "unit": None,
    }

    # Check for explicit "field equals value" condition
    eq_match = CONDITION_EQUALS_RE.search(text)
    if eq_match:
        condition["field"] = eq_match.group(1).strip()
        raw_value = eq_match.group(2).strip().rstrip('.')
        # Handle boolean-like values
        if raw_value.lower() in ("true", "false"):
            condition["value"] = raw_value.lower()
        else:
            condition["value"] = raw_value
        condition["operator"] = "EQUALS"
        condition["unit"] = None
        return condition

    # Check for "field older than X years" pattern
    field_match = FIELD_OLDER_THAN_RE.search(text)
    if field_match:
        condition["field"] = field_match.group(1)

    # Check for time period
    time_match = TIME_PERIOD_RE.search(text)
    if time_match:
        condition["value"] = str(int(_parse_number(time_match.group(1))))
        condition["unit"] = _normalize_unit(time_match.group(2))
        condition["operator"] = "OLDER_THAN"

        # Try to find the field name near the time period
        if condition["field"] == "unknown" or condition["field"] == policy.get("date_field", "unknown"):
            nearby_field = re.search(
                r'(\w+(?:_\w+)*)\s+(?:is\s+)?(?:older|more)\s+than',
                text, re.IGNORECASE,
            )
            if nearby_field:
                condition["field"] = nearby_field.group(1)

        # Use date field from policy if still unknown
        if condition["field"] == "unknown" and policy.get("date_field"):
            condition["field"] = policy["date_field"]

    # Check for "closed for more than X years" pattern
    closed_match = FIELD_CLOSED_RE.search(text)
    if closed_match:
        condition["value"] = str(int(_parse_number(closed_match.group(1))))
        condition["unit"] = _normalize_unit(closed_match.group(2))
        condition["operator"] = "OLDER_THAN"
        if policy.get("date_field"):
            condition["field"] = policy["date_field"]
        else:
            condition["field"] = "closed_date"

    # If we still have no value, check for "retained for at least X years"
    if not condition["value"]:
        retain_match = re.search(
            r'retained?\s+(?:for\s+)?(?:at\s+least\s+|a\s+minimum\s+of\s+)?'
            r'(\d+|one|two|three|four|five|six|seven|eight|nine|ten|'
            r'eleven|twelve|thirteen|fourteen|fifteen|twenty|thirty)\s+'
            r'(years?|months?|days?)',
            text, re.IGNORECASE,
        )
        if retain_match:
            condition["value"] = str(int(_parse_number(retain_match.group(1))))
            condition["unit"] = _normalize_unit(retain_match.group(2))

    return condition


def _infer_rule_type(operation: str | None) -> str:
    """Map operation to rule_type."""
    if operation in ("ARCHIVE", "DELETE"):
        return "ARCHIVAL"
    elif operation == "VERIFY":
        return "VERIFICATION"
    return "RETENTION"


def _parse_constraints(text: str, policy: dict):
    """Parse constraint bullet points."""
    items = re.findall(r'-\s+(.+?)(?=\n\s*-|\n\s*$|$)', text, re.DOTALL)
    for item in items:
        cleaned = re.sub(r'\s+', ' ', item).strip().rstrip('.')
        if cleaned:
            policy["constraints"].append(cleaned)


# ─── Main parser function ──────────────────────────────────────

def parse_policy_document(text: str) -> dict[str, Any]:
    """
    Parse a policy document using regex patterns.
    Returns a dict matching the same schema as the LLM analysis output.
    """
    logger.info("Starting regex-based policy parsing")

    # Extract the document-level metadata
    doc_name_match = re.search(
        r'^(.+?(?:POLICY|COMPLIANCE|REGULATION|STANDARD).+?)$',
        text, re.IGNORECASE | re.MULTILINE,
    )
    doc_name = doc_name_match.group(1).strip() if doc_name_match else "Policy Document"

    doc_id_match = re.search(r'Policy\s+Document\s+ID:\s*(\S+)', text, re.IGNORECASE)
    doc_id = doc_id_match.group(1) if doc_id_match else ""

    # Extract individual policy sections
    sections = _extract_policy_sections(text)
    global_requirements = _extract_global_requirements(text)

    # Parse each section
    all_rules = []
    all_exceptions = []
    all_ambiguities = []
    source_refs = []
    descriptions = []

    for idx, section in enumerate(sections):
        policy = _parse_policy_section(section["title"], section["body"], idx)

        all_rules.extend(policy["rules"])
        all_exceptions.extend(policy["exceptions"])

        if policy["description"]:
            descriptions.append(f"{policy['policy_name']}: {policy['description']}")

        if policy["source_system"]:
            source_refs.append(
                f"{policy['policy_name']}: {policy['source_system']} / {policy['source_table']}"
            )

        # Flag ambiguities — rules without values
        for rule in policy["rules"]:
            cond = rule.get("condition", {})
            if not cond.get("value"):
                all_ambiguities.append({
                    "type": "MISSING_THRESHOLD",
                    "severity": "MEDIUM",
                    "description": f"Rule {rule['rule_id']}: no threshold value found — '{rule['description'][:80]}'",
                    "requires_human_review": True,
                })
            if cond.get("field") == "unknown":
                all_ambiguities.append({
                    "type": "MISSING_FIELD",
                    "severity": "HIGH",
                    "description": f"Rule {rule['rule_id']}: could not identify the target field",
                    "requires_human_review": True,
                })

    # Build combined scope
    scopes = [s for s in source_refs if s]
    combined_scope = "; ".join(scopes) if scopes else "See individual policies"

    result = {
        "policy_name": doc_name,
        "scope": combined_scope,
        "description": " | ".join(descriptions) if descriptions else doc_name,
        "requirements": global_requirements,
        "rules": all_rules,
        "exceptions": all_exceptions,
        "ambiguities": all_ambiguities,
        "source_references": source_refs,
        "_parser": "regex",  # Marker to indicate regex parsing was used
        "_policies_found": len(sections),
    }

    logger.info(
        f"Regex parser extracted {len(all_rules)} rules, "
        f"{len(all_exceptions)} exceptions, "
        f"{len(all_ambiguities)} ambiguities from {len(sections)} policies"
    )

    return result

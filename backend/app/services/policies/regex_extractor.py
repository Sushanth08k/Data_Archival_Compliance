"""
Regex & heuristic-based policy extraction engine.
Extracts structured machine-executable rules, exceptions, and ambiguities
directly from policy documents without requiring an external LLM API.
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)

WORD_TO_NUM: dict[str, int] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "fifteen": 15,
    "twenty": 20,
    "thirty": 30,
}


def parse_numeric_value(val_str: str) -> str:
    """Normalize numeric strings like 'five' or '5' to '5'."""
    cleaned = val_str.strip().rstrip(".,;").lower()
    if cleaned in WORD_TO_NUM:
        return str(WORD_TO_NUM[cleaned])
    if cleaned.isdigit():
        return cleaned
    return cleaned


def extract_policy_with_regex(text: str) -> dict[str, Any]:
    """
    Extract structured rules, exceptions, and metadata from policy text
    using regular expressions and pattern matching heuristics.
    """
    if not text or not text.strip():
        raise ValueError("Policy text is empty")

    # 1. Extract Document Title / Name
    title = "Data Retention and Archival Policy"
    first_line_match = re.search(r"^(?:[#=\s]*)(.*?)(?:\n|$)", text.strip())
    if first_line_match:
        cand = first_line_match.group(1).strip().strip("=")
        if len(cand) > 3 and not cand.startswith("---"):
            title = cand

    # Extract Policy ID if present
    doc_id_match = re.search(r"Policy Document ID:\s*([^\n\r]+)", text, re.IGNORECASE)
    doc_id = doc_id_match.group(1).strip() if doc_id_match else None

    # 2. Check if text has distinct Policy sections
    section_pattern = re.compile(
        r"(?:={10,}\s*)?POLICY\s+(\d+):\s*([^\n\r]+)(.*?)(?=(?:={10,}\s*)?POLICY\s+\d+:|(?:={10,}\s*)?GLOBAL|$)",
        re.DOTALL | re.IGNORECASE,
    )
    sections = list(section_pattern.finditer(text))

    rules: list[dict[str, Any]] = []
    exceptions: list[dict[str, Any]] = []
    requirements: list[dict[str, Any]] = []
    ambiguities: list[dict[str, Any]] = []
    sources: list[str] = []
    scopes_found: list[str] = []

    if sections:
        # Structured multi-policy document
        for match in sections:
            p_num = match.group(1)
            p_title = match.group(2).strip()
            p_body = match.group(3).strip()

            scopes_found.append(p_title)

            # Table & date field
            table_m = re.search(r"Source table:\s*([a-zA-Z0-9_]+)", p_body, re.I)
            table_name = table_m.group(1).strip() if table_m else "records"

            date_field_m = re.search(
                r"(?:date field|closure field|creation date field|timestamp field):\s*([a-zA-Z0-9_]+)",
                p_body,
                re.I,
            )
            date_field = date_field_m.group(1).strip() if date_field_m else "created_at"

            # Parse rule blocks
            rule_blocks = re.findall(
                r"Rule\s+(\d+):\s*\n(.*?)(?=\n\s*(?:Rule\s+\d+:|Constraints:|$))",
                p_body,
                re.DOTALL | re.IGNORECASE,
            )

            for r_idx, r_body in rule_blocks:
                clean_body = " ".join(r_body.split())
                op_m = re.search(r"Operation:\s*(\w+)", r_body, re.I)
                op = op_m.group(1).upper() if op_m else "ARCHIVE"

                if op in ("ARCHIVE", "RETAIN", "DELETE"):
                    # Find age condition
                    age_m = re.search(
                        r"(?:older than|retained for (?:at least )?|more than|exceeding)\s+(\w+)\s+(years?|months?|days?)",
                        r_body,
                        re.I,
                    )
                    threshold = parse_numeric_value(age_m.group(1)) if age_m else "5"
                    unit = age_m.group(2).lower() if age_m else "years"
                    rule_type = "RETENTION" if op == "RETAIN" else "ARCHIVAL"

                    rules.append({
                        "rule_id": f"RULE-{len(rules) + 1:03d}",
                        "description": f"[{table_name}] {clean_body}",
                        "rule_type": rule_type,
                        "condition": {
                            "field": date_field,
                            "operator": "OLDER_THAN",
                            "value": threshold,
                            "unit": unit,
                        },
                        "action": "ARCHIVE" if op == "ARCHIVE" else op,
                    })
                    sources.append(clean_body)

                elif op == "EXCLUDE":
                    cond_m = re.search(
                        r"Condition:\s*\n?([a-zA-Z0-9_]+)\s+(?:equals|is|=)\s+([^\n\r\.]+)",
                        r_body,
                        re.I,
                    )
                    if cond_m:
                        ex_field = cond_m.group(1).strip()
                        ex_val = cond_m.group(2).strip()
                    else:
                        # Fallback heuristic
                        if "legal hold" in r_body.lower():
                            ex_field, ex_val = "legal_hold", "true"
                        elif "investigation" in r_body.lower():
                            ex_field, ex_val = "investigation_status", "ACTIVE"
                        else:
                            ex_field, ex_val = "excluded", "true"

                    exceptions.append({
                        "field": ex_field,
                        "operator": "EQUALS",
                        "value": ex_val,
                        "action": "EXCLUDE",
                        "reason": clean_body,
                    })
                    sources.append(clean_body)

                elif op in ("VERIFY", "REVIEW"):
                    rules.append({
                        "rule_id": f"RULE-{len(rules) + 1:03d}",
                        "description": f"[{table_name}] Verification requirement: {clean_body}",
                        "rule_type": "VERIFICATION",
                        "condition": {
                            "field": "archival_status",
                            "operator": "EQUALS",
                            "value": "VERIFIED",
                            "unit": None,
                        },
                        "action": "VERIFY",
                    })
                    sources.append(clean_body)

    # 3. If no structured sections or rules were found, use general regex parsing
    if not rules:
        # Search for general retention statements: "older than 5 years", "retained for 7 years"
        retention_matches = list(re.finditer(
            r"(?:records?|data|documents?|accounts?|transactions?|logs?)\s+.*?(?:older than|retained for|more than)\s+(\w+)\s+(years?|months?|days?)",
            text,
            re.IGNORECASE,
        ))

        for idx, rm in enumerate(retention_matches):
            sentence = rm.group(0)
            threshold = parse_numeric_value(rm.group(1))
            unit = rm.group(2).lower()

            # Guess field name
            field_name = "created_at"
            if "transaction" in sentence.lower():
                field_name = "transaction_date"
            elif "closed" in sentence.lower() or "account" in sentence.lower():
                field_name = "closed_date"

            rules.append({
                "rule_id": f"RULE-{len(rules) + 1:03d}",
                "description": sentence.strip(),
                "rule_type": "ARCHIVAL",
                "condition": {
                    "field": field_name,
                    "operator": "OLDER_THAN",
                    "value": threshold,
                    "unit": unit,
                },
                "action": "ARCHIVE",
            })
            sources.append(sentence)

        # Search for exclusion / legal hold statements
        if re.search(r"legal\s+hold", text, re.I):
            exceptions.append({
                "field": "legal_hold",
                "operator": "EQUALS",
                "value": "true",
                "action": "EXCLUDE",
                "reason": "Records subject to legal hold must not be archived or deleted.",
            })

        if re.search(r"investigation", text, re.I):
            exceptions.append({
                "field": "investigation_status",
                "operator": "EQUALS",
                "value": "ACTIVE",
                "action": "EXCLUDE",
                "reason": "Records under active investigation are excluded from archival.",
            })

        # Verification rule
        if re.search(r"verif(?:ied|ication)", text, re.I):
            rules.append({
                "rule_id": f"RULE-{len(rules) + 1:03d}",
                "description": "Independent verification of archival before source record removal.",
                "rule_type": "VERIFICATION",
                "condition": {
                    "field": "archival_status",
                    "operator": "EQUALS",
                    "value": "VERIFIED",
                    "unit": None,
                },
                "action": "VERIFY",
            })

    # Default fallback rule if still nothing extracted
    if not rules:
        rules.append({
            "rule_id": "RULE-001",
            "description": "Default retention rule: Archive records older than 5 years",
            "rule_type": "ARCHIVAL",
            "condition": {
                "field": "created_at",
                "operator": "OLDER_THAN",
                "value": "5",
                "unit": "years",
            },
            "action": "ARCHIVE",
        })

    # 4. Extract Global Requirements
    req_matches = re.findall(r"(\d+)\.\s+([^\n\r]+(?:\n[^\n\r]+)*)", text)
    if req_matches:
        for r_num, r_text in req_matches[:8]:
            clean_req = " ".join(r_text.split())
            if len(clean_req) > 10 and not clean_req.startswith("=="):
                requirements.append({
                    "requirement_id": f"REQ-{len(requirements) + 1:03d}",
                    "description": clean_req,
                })
    else:
        requirements = [
            {"requirement_id": "REQ-001", "description": "Records must be retained per regulatory lifecycle periods."},
            {"requirement_id": "REQ-002", "description": "Independent verification required before source removal."},
            {"requirement_id": "REQ-003", "description": "Human approval required prior to cleanup execution."},
        ]

    # 5. Detect Ambiguities
    if not re.search(r"(?:archival database|approved archive|destination)", text, re.I):
        ambiguities.append({
            "type": "MISSING_ARCHIVE_DESTINATION",
            "severity": "MEDIUM",
            "description": "Specific archive database cluster destination not explicitly designated.",
            "requires_human_review": True,
        })

    scope_desc = ", ".join(scopes_found) if scopes_found else "All organizational transaction, account, and audit records"
    summary_desc = f"Policy '{title}' defines compliance retention and archival thresholds for {scope_desc}."

    return {
        "policy_name": title,
        "scope": scope_desc,
        "description": summary_desc,
        "requirements": requirements,
        "rules": rules,
        "exceptions": exceptions,
        "ambiguities": ambiguities,
        "source_references": sources[:10] if sources else [text[:200]],
    }

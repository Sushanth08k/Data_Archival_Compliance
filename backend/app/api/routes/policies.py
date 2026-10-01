"""
Policy routes — upload, list, get, analyze, get rules.
"""

import os
import json
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.database import get_db
from app.api.dependencies import get_current_user
from app.models.user import User
from app.models.policy import Policy, PolicyVersion
from app.models.rule import PolicyRule, PolicyException
from app.schemas.policy import (
    PolicyResponse,
    PolicyListResponse,
    PolicyVersionResponse,
    PolicyUploadResponse,
    AnalysisResponse,
    RuleResponse,
    ExceptionResponse,
    AmbiguityItem,
)
from app.services.documents.extractor import validate_upload, extract_text
from app.services.policies.analyzer import analyze_policy_text
from app.services.evidence.recorder import record_event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/policies", tags=["Policies"])


@router.post("/upload", response_model=PolicyUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_policy(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a policy document (PDF, DOCX, TXT, or MD)."""
    # Validate
    content = await file.read()
    is_valid, error = validate_upload(file.filename, len(content))
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Save file to disk
    upload_dir = settings.UPLOAD_DIR
    os.makedirs(upload_dir, exist_ok=True)
    file_id = str(uuid.uuid4())[:8]
    safe_name = f"{file_id}_{file.filename}"
    file_path = os.path.join(upload_dir, safe_name)

    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text
    try:
        extracted_text = extract_text(file_path)
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to extract text from document: {e}",
        )

    # Create Policy
    policy = Policy(
        name=file.filename,  # will be updated after LLM analysis
        description="",
        status="DRAFT",
        created_by=current_user.id,
    )
    db.add(policy)
    await db.flush()

    # Create PolicyVersion
    version = PolicyVersion(
        policy_id=policy.id,
        version=1,
        document_name=file.filename,
        document_path=file_path,
        extracted_text=extracted_text,
        analysis_status="PENDING",
    )
    db.add(version)
    await db.flush()

    # Record audit
    await record_event(
        db=db,
        event_type="POLICY_UPLOADED",
        actor_id=current_user.id,
        actor_email=current_user.email,
        policy_id=policy.id,
        policy_version_id=version.id,
        metadata={"document_name": file.filename, "text_length": len(extracted_text)},
    )

    return PolicyUploadResponse(
        policy_id=policy.id,
        policy_version_id=version.id,
        document_name=file.filename,
        message="Policy uploaded and text extracted. Call /policies/{id}/analyze to run AI analysis.",
    )


@router.get("", response_model=PolicyListResponse)
async def list_policies(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all policies."""
    result = await db.execute(select(Policy).order_by(Policy.created_at.desc()))
    policies = result.scalars().all()
    return PolicyListResponse(
        policies=[PolicyResponse.model_validate(p) for p in policies],
        total=len(policies),
    )


@router.get("/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific policy."""
    result = await db.execute(select(Policy).where(Policy.id == policy_id))
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return PolicyResponse.model_validate(policy)


@router.get("/{policy_id}/versions")
async def get_policy_versions(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all versions of a policy."""
    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version.desc())
    )
    versions = result.scalars().all()
    return [PolicyVersionResponse.model_validate(v) for v in versions]


@router.post("/{policy_id}/analyze")
async def analyze_policy(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run AI analysis on the latest version of a policy."""
    # Get latest version
    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version.desc())
    )
    version = result.scalars().first()
    if not version:
        raise HTTPException(status_code=404, detail="No policy version found")

    if not version.extracted_text:
        raise HTTPException(status_code=400, detail="No extracted text available for analysis")

    try:
        analysis = await analyze_policy_text(
            db=db,
            policy_version_id=version.id,
            extracted_text=version.extracted_text,
            actor_id=current_user.id,
            actor_email=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    # Build response
    return {
        "policy_version_id": version.id,
        "analysis_status": "COMPLETED",
        "analysis": analysis,
    }


@router.get("/{policy_id}/rules")
async def get_policy_rules(
    policy_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the structured rules and exceptions for a policy."""
    policy = await db.get(Policy, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Find latest version
    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.version.desc())
    )
    version = result.scalars().first()
    if not version:
        raise HTTPException(status_code=404, detail="No policy version found")

    # Get rules
    rules_result = await db.execute(
        select(PolicyRule)
        .where(PolicyRule.policy_version_id == version.id)
        .order_by(PolicyRule.priority)
    )
    rules = rules_result.scalars().all()

    # Get exceptions
    exc_result = await db.execute(
        select(PolicyException)
        .where(PolicyException.policy_version_id == version.id)
    )
    exceptions = exc_result.scalars().all()

    # Get ambiguities from analysis result
    ambiguities = []
    if version.analysis_result:
        try:
            analysis_data = json.loads(version.analysis_result)
            ambiguities = analysis_data.get("ambiguities", [])
        except json.JSONDecodeError:
            pass

    return AnalysisResponse(
        policy_version_id=version.id,
        analysis_status=version.analysis_status,
        policy_name=policy.name,
        scope=policy.scope,
        description=policy.description,
        rules_count=len(rules),
        exceptions_count=len(exceptions),
        ambiguities_count=len(ambiguities),
        rules=[RuleResponse.model_validate(r) for r in rules],
        exceptions=[ExceptionResponse.model_validate(e) for e in exceptions],
        ambiguities=[AmbiguityItem(**a) for a in ambiguities] if ambiguities else [],
    )


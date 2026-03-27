"""Policy management API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Policy, PolicyAssignment, PolicyVersion
from app.schemas import (
    PaginatedResponse,
    PolicyAssignmentCreate,
    PolicyAssignmentResponse,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
    PolicyVersionResponse,
)

router = APIRouter(prefix="/admin/api", tags=["policies"])


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Policy).order_by(Policy.name))
    ).scalars().all()
    return rows


@router.post("/policies", response_model=PolicyResponse, status_code=201)
async def create_policy(
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    policy = Policy(
        name=body.name,
        tier=body.tier,
        description=body.description,
        yaml=body.yaml,
        current_version="1.0.0",
        created_at=now,
        updated_at=now,
    )
    db.add(policy)
    await db.flush()

    # Create initial version
    version = PolicyVersion(
        policy_id=policy.id,
        version="1.0.0",
        yaml=body.yaml,
        changelog="Initial version",
        created_at=now,
    )
    db.add(version)
    await db.flush()
    await db.refresh(policy)
    return policy


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(Policy).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")
    return row


@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(Policy).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    now = datetime.now(timezone.utc)

    if body.name is not None:
        row.name = body.name
    if body.tier is not None:
        row.tier = body.tier
    if body.description is not None:
        row.description = body.description

    # If YAML changed, bump version and create a new PolicyVersion record
    if body.yaml is not None and body.yaml != row.yaml:
        row.yaml = body.yaml
        # Simple semver bump: increment patch
        parts = row.current_version.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        new_version = ".".join(parts)
        row.current_version = new_version

        version = PolicyVersion(
            policy_id=row.id,
            version=new_version,
            yaml=body.yaml,
            changelog=body.changelog or "",
            created_at=now,
        )
        db.add(version)

    row.updated_at = now
    await db.flush()
    await db.refresh(row)
    return row


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(Policy).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    await db.delete(row)
    await db.flush()


@router.get("/policies/{policy_id}/versions", response_model=list[PolicyVersionResponse])
async def list_policy_versions(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(PolicyVersion)
            .where(PolicyVersion.policy_id == policy_id)
            .order_by(PolicyVersion.created_at.desc())
        )
    ).scalars().all()
    return rows


@router.post("/policies/{policy_id}/validate")
async def validate_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Placeholder — real validation requires openshell integration."""
    row = (
        await db.execute(select(Policy).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"valid": True, "message": "Validation placeholder — openshell integration pending"}


# ---------------------------------------------------------------------------
# Policy Assignments
# ---------------------------------------------------------------------------


@router.get("/policies/assignments", response_model=list[PolicyAssignmentResponse])
async def list_assignments(
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    query = select(PolicyAssignment)
    if entity_type:
        query = query.where(PolicyAssignment.entity_type == entity_type)
    if entity_id:
        query = query.where(PolicyAssignment.entity_id == entity_id)
    query = query.order_by(PolicyAssignment.priority.desc())

    rows = (await db.execute(query)).scalars().all()
    return rows


@router.put("/policies/assignments", response_model=PolicyAssignmentResponse)
async def upsert_assignment(
    body: PolicyAssignmentCreate,
    db: AsyncSession = Depends(get_db),
):
    # Check for existing assignment with same entity
    existing = (
        await db.execute(
            select(PolicyAssignment).where(
                PolicyAssignment.entity_type == body.entity_type,
                PolicyAssignment.entity_id == body.entity_id,
            )
        )
    ).scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if existing:
        existing.policy_id = body.policy_id
        existing.priority = body.priority
        await db.flush()
        await db.refresh(existing)
        return existing

    assignment = PolicyAssignment(
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        policy_id=body.policy_id,
        priority=body.priority,
        created_at=now,
    )
    db.add(assignment)
    await db.flush()
    await db.refresh(assignment)
    return assignment

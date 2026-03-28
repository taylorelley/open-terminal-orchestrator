"""Policy management API routes."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Policy, PolicyAssignment, PolicyVersion, User
from app.schemas import (
    DryRunRequest,
    PaginatedResponse,
    PolicyAssignmentCreate,
    PolicyAssignmentResponse,
    PolicyCreate,
    PolicyDiffResponse,
    PolicyResponse,
    PolicyUpdate,
    PolicyVersionResponse,
)
from app.services.admin_auth import require_admin
from app.services.audit_service import log_admin
from app.services.policy_engine import (
    classify_policy_changes,
    diff_policy_yaml,
    mark_sandboxes_for_recreation,
    propagate_policy_to_sandboxes,
    resolve_policy_for_user,
    validate_policy_yaml,
)

router = APIRouter(
    prefix="/admin/api",
    tags=["policies"],
    dependencies=[Depends(require_admin)],
)


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(select(Policy).order_by(Policy.name))
    ).scalars().all()
    return rows


@router.post("/policies", response_model=PolicyResponse, status_code=201)
async def create_policy(
    request: Request,
    body: PolicyCreate,
    db: AsyncSession = Depends(get_db),
):
    if body.yaml:
        valid, errors = validate_policy_yaml(body.yaml)
        if not valid:
            raise HTTPException(status_code=422, detail={"errors": errors})

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

    log_admin(
        db, "policy_change",
        details={
            "action": "created",
            "policy_id": str(policy.id),
            "policy_name": body.name,
        },
        source_ip=request.client.host if request.client else "",
    )

    await db.flush()
    await db.refresh(policy)
    return policy


# ---------------------------------------------------------------------------
# Inline validation (no policy_id) — must be registered before {policy_id}
# ---------------------------------------------------------------------------


@router.post("/policies/validate")
async def validate_policy_inline(body: dict):
    """Validate arbitrary policy YAML without requiring a saved policy."""
    yaml_str = body.get("yaml", "")
    if not yaml_str:
        return {"valid": False, "errors": ["No YAML provided"]}
    valid, errors = validate_policy_yaml(yaml_str)
    return {"valid": valid, "errors": errors}


# ---------------------------------------------------------------------------
# Policy Assignments — must be registered before {policy_id} routes
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
    request: Request,
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
    source_ip = request.client.host if request.client else ""

    if existing:
        existing.policy_id = body.policy_id
        existing.priority = body.priority
        log_admin(
            db, "policy_change",
            details={
                "action": "assignment_updated",
                "entity_type": body.entity_type,
                "entity_id": body.entity_id,
                "policy_id": str(body.policy_id),
            },
            source_ip=source_ip,
        )
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
    log_admin(
        db, "policy_change",
        details={
            "action": "assignment_created",
            "entity_type": body.entity_type,
            "entity_id": body.entity_id,
            "policy_id": str(body.policy_id),
        },
        source_ip=source_ip,
    )
    await db.flush()
    await db.refresh(assignment)
    return assignment


# ---------------------------------------------------------------------------
# Policy resolution — must be registered before {policy_id} routes
# ---------------------------------------------------------------------------


async def _determine_resolution_source(
    user: User,
    policy: Policy,
    db: AsyncSession,
) -> str:
    """Determine which level of the cascade resolved *policy* for *user*."""
    # Check user-level assignment
    row = (
        await db.execute(
            select(PolicyAssignment).where(
                PolicyAssignment.entity_type == "user",
                PolicyAssignment.entity_id == str(user.id),
            )
        )
    ).scalar_one_or_none()
    if row and row.policy_id == policy.id:
        return "user"

    # Check group-level assignment
    if user.group_id is not None:
        row = (
            await db.execute(
                select(PolicyAssignment).where(
                    PolicyAssignment.entity_type == "group",
                    PolicyAssignment.entity_id == str(user.group_id),
                )
            )
        ).scalar_one_or_none()
        if row and row.policy_id == policy.id:
            return "group"

    # Check role-level assignment
    row = (
        await db.execute(
            select(PolicyAssignment).where(
                PolicyAssignment.entity_type == "role",
                PolicyAssignment.entity_id == user.owui_role,
            )
        )
    ).scalar_one_or_none()
    if row and row.policy_id == policy.id:
        return "role"

    return "default"


@router.get("/policies/resolve/{uid}")
async def resolve_user_policy(
    uid: str,
    db: AsyncSession = Depends(get_db),
):
    """Resolve the effective policy for a user by their Open WebUI user ID."""
    user = (
        await db.execute(select(User).where(User.owui_id == uid))
    ).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    policy = await resolve_policy_for_user(user, db)
    if not policy:
        return {"user_id": str(user.id), "owui_id": uid, "policy": None, "source": None}

    source = await _determine_resolution_source(user, policy, db)
    return {
        "user_id": str(user.id),
        "owui_id": uid,
        "policy": PolicyResponse.model_validate(policy),
        "source": source,
    }


# ---------------------------------------------------------------------------
# Per-policy routes (parameterised by {policy_id})
# ---------------------------------------------------------------------------


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
    request: Request,
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

    # If YAML changed, validate, bump version and create a new PolicyVersion record
    hot_reloaded_count = 0
    recreation_scheduled = 0
    yaml_changed = body.yaml is not None and body.yaml != row.yaml

    if yaml_changed:
        assert body.yaml is not None  # for type narrowing
        valid, errors = validate_policy_yaml(body.yaml)
        if not valid:
            raise HTTPException(status_code=422, detail={"errors": errors})

        old_yaml = row.yaml
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

        # Classify changes and propagate/schedule recreation accordingly.
        source_ip = request.client.host if request.client else ""
        has_dynamic, has_static = classify_policy_changes(old_yaml, body.yaml)

        if has_static:
            # Static sections changed — sandboxes must be recreated.
            recreation_scheduled = await mark_sandboxes_for_recreation(row.id, db)
        elif has_dynamic:
            # Only dynamic sections changed — hot-reload on live sandboxes.
            updated_ids = await propagate_policy_to_sandboxes(
                row, db, source_ip=source_ip,
            )
            hot_reloaded_count = len(updated_ids)

    row.updated_at = now

    changes = [k for k in ("name", "tier", "description", "yaml") if getattr(body, k, None) is not None]
    log_admin(
        db, "policy_change",
        details={
            "action": "updated",
            "policy_id": str(policy_id),
            "policy_name": row.name,
            "changes": changes,
            "hot_reloaded_count": hot_reloaded_count,
            "recreation_scheduled": recreation_scheduled,
        },
        source_ip=request.client.host if request.client else "",
    )

    await db.flush()
    await db.refresh(row)
    return row


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_policy(
    policy_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    row = (
        await db.execute(select(Policy).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    log_admin(
        db, "policy_change",
        details={
            "action": "deleted",
            "policy_id": str(policy_id),
            "policy_name": row.name,
        },
        source_ip=request.client.host if request.client else "",
    )

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


@router.get("/policies/{policy_id}/versions/{version}", response_model=PolicyVersionResponse)
async def get_policy_version(
    policy_id: uuid.UUID,
    version: str,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve a specific version of a policy by version string."""
    row = (
        await db.execute(
            select(PolicyVersion).where(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.version == version,
            )
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Version not found")
    return row


@router.get("/policies/{policy_id}/diff", response_model=PolicyDiffResponse)
async def diff_policy_versions(
    policy_id: uuid.UUID,
    from_version: str = Query(..., description="Source version string"),
    to_version: str = Query(..., description="Target version string"),
    db: AsyncSession = Depends(get_db),
):
    """Return a structured diff between two versions of a policy."""
    from_row = (
        await db.execute(
            select(PolicyVersion).where(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.version == from_version,
            )
        )
    ).scalar_one_or_none()
    if not from_row:
        raise HTTPException(status_code=404, detail=f"Version '{from_version}' not found")

    to_row = (
        await db.execute(
            select(PolicyVersion).where(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.version == to_version,
            )
        )
    ).scalar_one_or_none()
    if not to_row:
        raise HTTPException(status_code=404, detail=f"Version '{to_version}' not found")

    result = diff_policy_yaml(from_row.yaml, to_row.yaml)
    return PolicyDiffResponse(
        from_version=from_version,
        to_version=to_version,
        **result,
    )


@router.post("/policies/{policy_id}/validate")
async def validate_policy(
    policy_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Validate the policy YAML against the expected schema."""
    row = (
        await db.execute(select(Policy).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    valid, errors = validate_policy_yaml(row.yaml)
    return {"valid": valid, "errors": errors}


@router.post("/policies/{policy_id}/dry-run")
async def dry_run_policy_endpoint(
    policy_id: uuid.UUID,
    body: DryRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Test a policy against an OpenShell sandbox without applying it."""
    import json
    import tempfile
    from pathlib import Path

    from app.services import openshell_client

    row = (
        await db.execute(select(Policy).where(Policy.id == policy_id))
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    valid, errors = validate_policy_yaml(row.yaml)
    if not valid:
        raise HTTPException(status_code=422, detail={"errors": errors})

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix=f"sg-dryrun-{policy_id.hex[:8]}-",
            suffix=".yaml",
            delete=False,
        ) as tmp:
            tmp.write(row.yaml)
            tmp_path = tmp.name

        raw = await openshell_client.dry_run_policy(body.sandbox_name, tmp_path)
        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {"output": raw}

        return {"policy_id": str(policy_id), "sandbox_name": body.sandbox_name, "result": result}

    except openshell_client.OpenShellError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    finally:
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)


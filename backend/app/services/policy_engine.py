"""Policy resolution, validation, and application engine.

Handles:
- Resolving the effective policy for a user via priority cascade
  (user → group → role → system default).
- Structural validation of policy YAML against the expected schema.
- Applying a resolved policy to a sandbox via the openshell CLI.
"""

import logging
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Policy, PolicyAssignment, Sandbox, SystemConfig, User
from app.services import openshell_client
from app.services.audit_service import log_enforcement

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# YAML validation
# ---------------------------------------------------------------------------

_VALID_DEFAULTS = {"allow", "deny"}
_VALID_TIERS = {"restricted", "standard", "elevated"}


def validate_policy_yaml(yaml_str: str) -> tuple[bool, list[str]]:
    """Validate policy YAML structure.

    Returns ``(is_valid, errors)`` where *errors* is a list of human-readable
    validation messages.  An empty *errors* list means the YAML is valid.
    """
    errors: list[str] = []

    # --- parse ---
    try:
        doc = yaml.safe_load(yaml_str)
    except yaml.YAMLError as exc:
        return False, [f"Invalid YAML syntax: {exc}"]

    if not isinstance(doc, dict):
        return False, ["Policy must be a YAML mapping (key-value pairs)"]

    # --- metadata (required) ---
    metadata = doc.get("metadata")
    if not isinstance(metadata, dict):
        errors.append("Missing or invalid 'metadata' section (must be a mapping)")
    else:
        for field in ("name", "tier", "version"):
            if field not in metadata:
                errors.append(f"metadata.{field} is required")
        tier = metadata.get("tier")
        if tier is not None and tier not in _VALID_TIERS:
            errors.append(
                f"metadata.tier must be one of {sorted(_VALID_TIERS)}, got '{tier}'"
            )

    # Must have at least one policy section
    has_section = any(k in doc for k in ("network", "filesystem", "process"))
    if not has_section:
        errors.append(
            "Policy must contain at least one of: 'network', 'filesystem', 'process'"
        )

    # --- network ---
    _validate_network(doc.get("network"), errors)

    # --- filesystem ---
    _validate_filesystem(doc.get("filesystem"), errors)

    # --- process ---
    _validate_process(doc.get("process"), errors)

    return len(errors) == 0, errors


def _validate_network(section: Any, errors: list[str]) -> None:
    if section is None:
        return
    if not isinstance(section, dict):
        errors.append("'network' must be a mapping")
        return

    default = section.get("default")
    if default is not None and default not in _VALID_DEFAULTS:
        errors.append(f"network.default must be 'allow' or 'deny', got '{default}'")

    egress = section.get("egress")
    if egress is not None and not isinstance(egress, list):
        errors.append("network.egress must be a list")


def _validate_filesystem(section: Any, errors: list[str]) -> None:
    if section is None:
        return
    if not isinstance(section, dict):
        errors.append("'filesystem' must be a mapping")
        return

    default = section.get("default")
    if default is not None and default not in _VALID_DEFAULTS:
        errors.append(
            f"filesystem.default must be 'allow' or 'deny', got '{default}'"
        )

    for key in ("writable", "readable"):
        value = section.get(key)
        if value is None:
            continue
        if not isinstance(value, list):
            errors.append(f"filesystem.{key} must be a list of paths")
        elif not all(isinstance(p, str) for p in value):
            errors.append(f"filesystem.{key} entries must be strings")


def _validate_process(section: Any, errors: list[str]) -> None:
    if section is None:
        return
    if not isinstance(section, dict):
        errors.append("'process' must be a mapping")
        return

    for key in ("allow_sudo", "allow_ptrace"):
        value = section.get(key)
        if value is not None and not isinstance(value, bool):
            errors.append(f"process.{key} must be a boolean, got {type(value).__name__}")


# ---------------------------------------------------------------------------
# Policy resolution
# ---------------------------------------------------------------------------


async def resolve_policy_for_user(
    user: User,
    db: AsyncSession,
) -> Policy | None:
    """Resolve the effective policy for *user* using the priority cascade.

    Resolution order (highest priority wins):
      1. User-level assignment  (entity_type='user',  priority 30)
      2. Group-level assignment (entity_type='group', priority 20)
      3. Role-level assignment  (entity_type='role',  priority 10)
      4. System default policy  (system_config key 'default_policy_id')

    Returns the :class:`Policy` object or ``None`` if no policy applies.
    """

    # 1. User-level assignment
    policy = await _lookup_assignment(db, "user", str(user.id))
    if policy is not None:
        logger.debug("Resolved user-level policy '%s' for user %s", policy.name, user.owui_id)
        return policy

    # 2. Group-level assignment
    if user.group_id is not None:
        policy = await _lookup_assignment(db, "group", str(user.group_id))
        if policy is not None:
            logger.debug("Resolved group-level policy '%s' for user %s", policy.name, user.owui_id)
            return policy

    # 3. Role-level assignment
    policy = await _lookup_assignment(db, "role", user.owui_role)
    if policy is not None:
        logger.debug("Resolved role-level policy '%s' for user %s", policy.name, user.owui_id)
        return policy

    # 4. System default
    policy = await _lookup_default_policy(db)
    if policy is not None:
        logger.debug("Resolved system default policy '%s' for user %s", policy.name, user.owui_id)
    else:
        logger.debug("No policy resolved for user %s", user.owui_id)

    return policy


async def _lookup_assignment(
    db: AsyncSession,
    entity_type: str,
    entity_id: str,
) -> Policy | None:
    """Find the policy assigned to an entity via ``policy_assignments``."""
    result = await db.execute(
        select(PolicyAssignment)
        .where(
            PolicyAssignment.entity_type == entity_type,
            PolicyAssignment.entity_id == entity_id,
        )
        .order_by(PolicyAssignment.priority.desc())
        .limit(1)
    )
    assignment = result.scalar_one_or_none()
    if assignment is None:
        return None

    # Eagerly loaded via relationship; fall back to explicit fetch.
    if assignment.policy is not None:
        return assignment.policy

    policy = (
        await db.execute(select(Policy).where(Policy.id == assignment.policy_id))
    ).scalar_one_or_none()
    return policy


async def _lookup_default_policy(db: AsyncSession) -> Policy | None:
    """Read the system default policy from ``system_config``."""
    row = (
        await db.execute(
            select(SystemConfig).where(SystemConfig.key == "default_policy_id")
        )
    ).scalar_one_or_none()
    if row is None:
        return None

    policy_id = row.value.get("policy_id") if isinstance(row.value, dict) else None
    if policy_id is None:
        return None

    try:
        pid = uuid.UUID(str(policy_id))
    except ValueError:
        logger.warning("Invalid default_policy_id value: %s", policy_id)
        return None

    return (
        await db.execute(select(Policy).where(Policy.id == pid))
    ).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Policy application
# ---------------------------------------------------------------------------


async def apply_policy_to_sandbox(
    sandbox: Sandbox,
    policy: Policy,
    db: AsyncSession,
    *,
    source_ip: str = "",
) -> None:
    """Write the policy YAML to a temp file and apply it via ``openshell policy set``.

    Updates ``sandbox.policy_id`` and logs an audit event on success.
    """
    tmp_path: str | None = None
    try:
        # Write YAML to a temp file (openshell expects a file path).
        with tempfile.NamedTemporaryFile(
            mode="w",
            prefix=f"sg-policy-{sandbox.id.hex[:8]}-",
            suffix=".yaml",
            delete=False,
        ) as tmp:
            tmp.write(policy.yaml)
            tmp_path = tmp.name

        await openshell_client.set_policy(sandbox.name, tmp_path)

        sandbox.policy_id = policy.id
        log_enforcement(
            db, "policy_applied",
            user_id=sandbox.user_id,
            sandbox_id=sandbox.id,
            details={
                "policy_id": str(policy.id),
                "policy_name": policy.name,
                "policy_version": policy.current_version,
            },
            source_ip=source_ip,
        )
        await db.flush()
        logger.info(
            "Applied policy '%s' (v%s) to sandbox %s",
            policy.name,
            policy.current_version,
            sandbox.name,
        )

    except Exception:
        logger.exception(
            "Failed to apply policy '%s' to sandbox %s",
            policy.name,
            sandbox.name,
        )
        raise

    finally:
        if tmp_path is not None:
            Path(tmp_path).unlink(missing_ok=True)

"""Initial ShellGuard schema.

Revision ID: 0001
Revises:
Create Date: 2026-03-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("tier", sa.Text(), nullable=False, server_default="restricted"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("current_version", sa.Text(), nullable=False, server_default="1.0.0"),
        sa.Column("yaml", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "policy_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("yaml", sa.Text(), nullable=False, server_default=""),
        sa.Column("changelog", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_policy_versions_policy_id", "policy_versions", ["policy_id"])

    op.create_table(
        "groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owui_id", sa.Text(), nullable=False, unique=True),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False, server_default=""),
        sa.Column("owui_role", sa.Text(), nullable=False, server_default="user"),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_users_group_id", "users", ["group_id"])

    op.create_table(
        "sandboxes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("state", sa.Text(), nullable=False, server_default="POOL"),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("internal_ip", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_tag", sa.Text(), nullable=False, server_default="shellguard-sandbox:slim"),
        sa.Column("gpu_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("cpu_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("memory_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("disk_usage", sa.Float(), nullable=False, server_default="0"),
        sa.Column("network_io", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("destroyed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_sandboxes_user_id", "sandboxes", ["user_id"])
    op.create_index("idx_sandboxes_state", "sandboxes", ["state"])
    op.create_index("idx_sandboxes_policy_id", "sandboxes", ["policy_id"])

    op.create_table(
        "policy_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("policies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_policy_assignments_entity", "policy_assignments", ["entity_type", "entity_id"])
    op.create_index("idx_policy_assignments_policy_id", "policy_assignments", ["policy_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sandbox_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sandboxes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("source_ip", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("idx_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("idx_audit_log_category", "audit_log", ["category"])
    op.create_index("idx_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("idx_audit_log_sandbox_id", "audit_log", ["sandbox_id"])

    op.create_table(
        "system_config",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("system_config")
    op.drop_table("audit_log")
    op.drop_table("policy_assignments")
    op.drop_table("sandboxes")
    op.drop_table("users")
    op.drop_table("groups")
    op.drop_table("policy_versions")
    op.drop_table("policies")

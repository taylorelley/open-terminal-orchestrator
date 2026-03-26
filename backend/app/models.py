"""SQLAlchemy ORM models mapped to the existing Supabase schema.

Schema is defined in: supabase/migrations/20260326203442_create_shellguard_schema.sql
These models are read/write adapters only — never call Base.metadata.create_all().
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tier: Mapped[str] = mapped_column(Text, nullable=False, default="restricted")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    current_version: Mapped[str] = mapped_column(Text, nullable=False, default="1.0.0")
    yaml: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    versions: Mapped[list["PolicyVersion"]] = relationship(back_populates="policy", lazy="selectin")


class PolicyVersion(Base):
    __tablename__ = "policy_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    yaml: Mapped[str] = mapped_column(Text, nullable=False, default="")
    changelog: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # References auth.users in Supabase — plain column here, no FK relationship.
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    policy: Mapped["Policy"] = relationship(back_populates="versions", lazy="selectin")


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    policy: Mapped["Policy | None"] = relationship(lazy="selectin")
    members: Mapped[list["User"]] = relationship(back_populates="group", lazy="selectin")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owui_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(Text, nullable=False, default="")
    owui_role: Mapped[str] = mapped_column(Text, nullable=False, default="user")
    group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("groups.id", ondelete="SET NULL"), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    group: Mapped["Group | None"] = relationship(back_populates="members", lazy="selectin")


class Sandbox(Base):
    __tablename__ = "sandboxes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    state: Mapped[str] = mapped_column(Text, nullable=False, default="POOL")
    policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id", ondelete="SET NULL"), nullable=True)
    internal_ip: Mapped[str] = mapped_column(Text, nullable=False, default="")
    image_tag: Mapped[str] = mapped_column(Text, nullable=False, default="shellguard-sandbox:slim")
    gpu_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    disk_usage: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    network_io: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User | None"] = relationship(lazy="selectin")
    policy: Mapped["Policy | None"] = relationship(lazy="selectin")


class PolicyAssignment(Base):
    __tablename__ = "policy_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[str] = mapped_column(Text, nullable=False)
    policy_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # References auth.users in Supabase — plain column here, no FK relationship.
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    policy: Mapped["Policy"] = relationship(lazy="selectin")


class AuditLogEntry(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    sandbox_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sandboxes.id", ondelete="SET NULL"), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    source_ip: Mapped[str] = mapped_column(Text, nullable=False, default="")

    user: Mapped["User | None"] = relationship(lazy="selectin")
    sandbox: Mapped["Sandbox | None"] = relationship(lazy="selectin")


class SystemConfig(Base):
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # References auth.users in Supabase — plain column here, no FK relationship.
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

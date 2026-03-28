"""Pydantic request/response schemas for the Management API."""

import uuid
from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class PolicyBase(BaseModel):
    name: str
    tier: str = "restricted"
    description: str = ""
    yaml: str = ""


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: str | None = None
    tier: str | None = None
    description: str | None = None
    yaml: str | None = None
    changelog: str = ""


class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    tier: str
    description: str
    current_version: str
    yaml: str
    created_at: datetime
    updated_at: datetime


class PolicyVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    policy_id: uuid.UUID
    version: str
    yaml: str
    changelog: str
    created_by: uuid.UUID | None
    created_at: datetime


class PolicyDiffDetail(BaseModel):
    old: dict | None = None
    new: dict | None = None


class PolicyDiffResponse(BaseModel):
    from_version: str
    to_version: str
    sections_changed: list[str]
    sections_added: list[str]
    sections_removed: list[str]
    has_dynamic_changes: bool
    has_static_changes: bool
    dynamic_sections_changed: list[str]
    static_sections_changed: list[str]
    metadata_changed: bool
    details: dict[str, PolicyDiffDetail]
    unified_diff: str


# ---------------------------------------------------------------------------
# Group
# ---------------------------------------------------------------------------


class GroupBase(BaseModel):
    name: str
    description: str = ""
    policy_id: uuid.UUID | None = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    policy_id: uuid.UUID | None = None


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    policy_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    policy: PolicyResponse | None = None


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owui_id: str
    username: str
    email: str
    owui_role: str
    group_id: uuid.UUID | None
    synced_at: datetime
    group: GroupResponse | None = None


class UserSyncResponse(BaseModel):
    status: str
    created: int
    updated: int
    unchanged: int
    total_remote: int
    message: str = ""


# ---------------------------------------------------------------------------
# Sandbox
# ---------------------------------------------------------------------------


class SandboxResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    user_id: uuid.UUID | None
    state: str
    policy_id: uuid.UUID | None
    internal_ip: str
    image_tag: str
    gpu_enabled: bool
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: float
    created_at: datetime
    last_active_at: datetime
    suspended_at: datetime | None
    destroyed_at: datetime | None
    pending_recreation: bool = False
    user: UserResponse | None = None
    policy: PolicyResponse | None = None


class SandboxUpdatePolicy(BaseModel):
    policy_id: uuid.UUID


# ---------------------------------------------------------------------------
# Policy Assignment
# ---------------------------------------------------------------------------


class PolicyAssignmentCreate(BaseModel):
    entity_type: str
    entity_id: str
    policy_id: uuid.UUID
    priority: int = 0


class PolicyAssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: str
    entity_id: str
    policy_id: uuid.UUID
    priority: int
    created_by: uuid.UUID | None
    created_at: datetime
    policy: PolicyResponse | None = None


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp: datetime
    event_type: str
    category: str
    user_id: uuid.UUID | None
    sandbox_id: uuid.UUID | None
    details: dict
    source_ip: str
    user: UserResponse | None = None
    sandbox: SandboxResponse | None = None


# ---------------------------------------------------------------------------
# System Config
# ---------------------------------------------------------------------------


class SystemConfigResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: dict
    updated_at: datetime
    updated_by: uuid.UUID | None


class SystemConfigUpdate(BaseModel):
    value: dict


# ---------------------------------------------------------------------------
# Pool Status
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Proxy
# ---------------------------------------------------------------------------


class ProxyErrorResponse(BaseModel):
    error: str
    status: str | None = None
    retry_after: int | None = None


# ---------------------------------------------------------------------------
# Pool Status
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------


class WebhookEventFilter(BaseModel):
    category: str | None = None
    event_type: str | None = None


class WebhookConfigCreate(BaseModel):
    url: str
    secret: str = ""
    enabled: bool = True
    event_filters: list[WebhookEventFilter] = []


class WebhookConfigResponse(BaseModel):
    index: int
    url: str
    enabled: bool
    event_filters: list[WebhookEventFilter] = []


class WebhookConfigUpdate(BaseModel):
    url: str | None = None
    secret: str | None = None
    enabled: bool | None = None
    event_filters: list[WebhookEventFilter] | None = None


# ---------------------------------------------------------------------------
# Syslog
# ---------------------------------------------------------------------------


class SyslogConfigResponse(BaseModel):
    host: str
    port: int
    protocol: str
    facility: int
    app_name: str


class SyslogConfigUpdate(BaseModel):
    host: str
    port: int = 514
    protocol: str = "udp"
    facility: int = 1
    app_name: str = "shellguard"


class PoolStatusResponse(BaseModel):
    total: int = 0
    active: int = 0
    ready: int = 0
    warming: int = 0
    suspended: int = 0
    pool: int = 0
    max_sandboxes: int = Field(default=0, description="From system_config pool.max_sandboxes")
    max_active: int = Field(default=0, description="From system_config pool.max_active")
    warmup_size: int = Field(default=0, description="From system_config pool.warmup_size")

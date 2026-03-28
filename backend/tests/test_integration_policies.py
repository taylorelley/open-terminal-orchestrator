"""Integration tests for the policy management API routes (/admin/api/policies/*)."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import (
    _make_result_scalar_one_or_none,
    _make_result_scalars_all,
)


class TestListPolicies:
    @pytest.mark.asyncio
    async def test_returns_policies(self, client, mock_db, make_policy):
        p1 = make_policy(name="policy-a")
        p2 = make_policy(name="policy-b")

        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([p1, p2]))

        resp = await client.get("/admin/api/policies")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        assert data[0]["name"] == "policy-a"

    @pytest.mark.asyncio
    async def test_empty_list(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([]))

        resp = await client.get("/admin/api/policies")

        assert resp.status_code == 200
        assert resp.json() == []


class TestCreatePolicy:
    @pytest.mark.asyncio
    @patch("app.routes.policies.log_admin")
    async def test_create_minimal_policy(self, mock_log, client, mock_db):
        created_policy = None

        def capture_add(obj):
            nonlocal created_policy
            if hasattr(obj, "name") and hasattr(obj, "tier"):
                created_policy = obj

        mock_db.add = capture_add

        async def mock_refresh(obj):
            # Simulate the DB assigning an ID and keeping attributes
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()

        mock_db.refresh = mock_refresh

        resp = await client.post(
            "/admin/api/policies",
            json={"name": "new-policy", "tier": "permissive"},
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new-policy"
        assert data["tier"] == "permissive"

    @pytest.mark.asyncio
    async def test_create_policy_invalid_yaml_returns_422(self, client, mock_db):
        resp = await client.post(
            "/admin/api/policies",
            json={"name": "bad", "yaml": "not: [valid: yaml: {"},
        )

        assert resp.status_code == 422


class TestGetPolicy:
    @pytest.mark.asyncio
    async def test_returns_policy(self, client, mock_db, make_policy):
        p = make_policy(name="found-policy")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(p))

        resp = await client.get(f"/admin/api/policies/{p.id}")

        assert resp.status_code == 200
        assert resp.json()["name"] == "found-policy"

    @pytest.mark.asyncio
    async def test_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.get(f"/admin/api/policies/{uuid.uuid4()}")

        assert resp.status_code == 404


class TestUpdatePolicy:
    @pytest.mark.asyncio
    @patch("app.routes.policies.log_admin")
    async def test_update_name_only(self, mock_log, client, mock_db, make_policy):
        p = make_policy(name="old-name")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(p))

        resp = await client.put(
            f"/admin/api/policies/{p.id}",
            json={"name": "new-name"},
        )

        assert resp.status_code == 200
        assert p.name == "new-name"

    @pytest.mark.asyncio
    async def test_update_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.put(
            f"/admin/api/policies/{uuid.uuid4()}",
            json={"name": "x"},
        )

        assert resp.status_code == 404


class TestDeletePolicy:
    @pytest.mark.asyncio
    @patch("app.routes.policies.log_admin")
    async def test_delete_policy(self, mock_log, client, mock_db, make_policy):
        p = make_policy()
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(p))

        resp = await client.delete(f"/admin/api/policies/{p.id}")

        assert resp.status_code == 204
        mock_db.delete.assert_awaited_once_with(p)

    @pytest.mark.asyncio
    async def test_delete_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.delete(f"/admin/api/policies/{uuid.uuid4()}")

        assert resp.status_code == 404


class TestPolicyVersions:
    @pytest.mark.asyncio
    async def test_returns_versions(self, client, mock_db):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        v1 = SimpleNamespace(
            id=uuid.uuid4(),
            policy_id=uuid.uuid4(),
            version="1.0.0",
            yaml="",
            changelog="Initial",
            created_by=None,
            created_at=now,
            policy=None,
        )

        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([v1]))

        resp = await client.get(f"/admin/api/policies/{v1.policy_id}/versions")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["version"] == "1.0.0"


class TestPolicyDiff:
    @pytest.mark.asyncio
    async def test_diff_between_versions(self, client, mock_db):
        from datetime import datetime, timezone

        policy_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        v1 = SimpleNamespace(
            id=uuid.uuid4(), policy_id=policy_id, version="1.0.0",
            yaml="metadata:\n  name: test\nnetwork:\n  egress: allow-all\n",
            changelog="", created_by=None, created_at=now,
        )
        v2 = SimpleNamespace(
            id=uuid.uuid4(), policy_id=policy_id, version="1.0.1",
            yaml="metadata:\n  name: test\nnetwork:\n  egress: deny-all\n",
            changelog="", created_by=None, created_at=now,
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(v1),
                _make_result_scalar_one_or_none(v2),
            ]
        )

        resp = await client.get(
            f"/admin/api/policies/{policy_id}/diff",
            params={"from_version": "1.0.0", "to_version": "1.0.1"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["from_version"] == "1.0.0"
        assert data["to_version"] == "1.0.1"
        assert "network" in data["sections_changed"]

    @pytest.mark.asyncio
    async def test_diff_version_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.get(
            f"/admin/api/policies/{uuid.uuid4()}/diff",
            params={"from_version": "1.0.0", "to_version": "2.0.0"},
        )

        assert resp.status_code == 404


class TestValidatePolicy:
    @pytest.mark.asyncio
    async def test_validate_inline_valid(self, client, mock_db):
        yaml_str = "metadata:\n  name: test\n  tier: restricted\n  version: '1.0'\nnetwork:\n  default: deny\nfilesystem:\n  default: deny\n  writable:\n    - /tmp\nprocess:\n  allow_sudo: false\n"

        resp = await client.post(
            "/admin/api/policies/validate",
            json={"yaml": yaml_str},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_inline_invalid(self, client, mock_db):
        resp = await client.post(
            "/admin/api/policies/validate",
            json={"yaml": "not valid yaml: {["},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    @pytest.mark.asyncio
    async def test_validate_stored_policy(self, client, mock_db, make_policy):
        p = make_policy(yaml="metadata:\n  name: test\n  tier: restricted\n  version: '1.0'\nnetwork:\n  default: deny\nfilesystem:\n  default: deny\n  writable:\n    - /tmp\nprocess:\n  allow_sudo: false\n")
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(p))

        resp = await client.post(f"/admin/api/policies/{p.id}/validate")

        assert resp.status_code == 200
        assert resp.json()["valid"] is True


class TestPolicyAssignments:
    @pytest.mark.asyncio
    async def test_list_assignments(self, client, mock_db):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        assignment = SimpleNamespace(
            id=uuid.uuid4(),
            entity_type="user",
            entity_id="user-1",
            policy_id=uuid.uuid4(),
            priority=30,
            created_by=None,
            created_at=now,
            policy=None,
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalars_all([assignment]))

        resp = await client.get("/admin/api/policies/assignments")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["entity_type"] == "user"

    @pytest.mark.asyncio
    @patch("app.routes.policies.log_admin")
    async def test_create_assignment(self, mock_log, client, mock_db):
        policy_id = uuid.uuid4()

        # First call: check existing; it returns None (no existing assignment)
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        # Capture the added object
        added = []
        mock_db.add = lambda obj: added.append(obj)

        async def mock_refresh(obj):
            if not hasattr(obj, "id") or obj.id is None:
                obj.id = uuid.uuid4()
            if not hasattr(obj, "created_at"):
                from datetime import datetime, timezone
                obj.created_at = datetime.now(timezone.utc)
            if not hasattr(obj, "created_by"):
                obj.created_by = None
            if not hasattr(obj, "policy"):
                obj.policy = None

        mock_db.refresh = mock_refresh

        resp = await client.put(
            "/admin/api/policies/assignments",
            json={
                "entity_type": "user",
                "entity_id": "user-1",
                "policy_id": str(policy_id),
                "priority": 30,
            },
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "user"
        assert data["policy_id"] == str(policy_id)


class TestGetPolicyVersion:
    """R4: GET /admin/api/policies/{id}/versions/{v}"""

    @pytest.mark.asyncio
    async def test_returns_specific_version(self, client, mock_db):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        policy_id = uuid.uuid4()
        v = SimpleNamespace(
            id=uuid.uuid4(),
            policy_id=policy_id,
            version="1.0.2",
            yaml="metadata:\n  name: test\n",
            changelog="Bugfix",
            created_by=None,
            created_at=now,
            policy=None,
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(v))

        resp = await client.get(f"/admin/api/policies/{policy_id}/versions/1.0.2")

        assert resp.status_code == 200
        data = resp.json()
        assert data["version"] == "1.0.2"
        assert data["changelog"] == "Bugfix"

    @pytest.mark.asyncio
    async def test_version_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.get(f"/admin/api/policies/{uuid.uuid4()}/versions/9.9.9")

        assert resp.status_code == 404


class TestResolveUserPolicy:
    """R5: GET /admin/api/policies/resolve/{uid}"""

    @pytest.mark.asyncio
    async def test_user_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.get("/admin/api/policies/resolve/owui-unknown")

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_no_policy_resolved(self, client, mock_db, make_user):
        user = make_user(owui_id="owui-test123")

        # 1st call: user lookup; remaining calls: assignment lookups (all return None)
        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(user),  # user lookup
                _make_result_scalar_one_or_none(None),   # user assignment
                _make_result_scalar_one_or_none(None),   # role assignment
                _make_result_scalar_one_or_none(None),   # default policy
            ]
        )

        resp = await client.get("/admin/api/policies/resolve/owui-test123")

        assert resp.status_code == 200
        data = resp.json()
        assert data["owui_id"] == "owui-test123"
        assert data["policy"] is None

    @pytest.mark.asyncio
    async def test_resolves_user_level_policy(self, client, mock_db, make_user, make_policy):
        from datetime import datetime, timezone

        user = make_user(owui_id="owui-resolved")
        policy = make_policy(name="user-policy")

        assignment = SimpleNamespace(
            id=uuid.uuid4(),
            entity_type="user",
            entity_id=str(user.id),
            policy_id=policy.id,
            priority=30,
            created_by=None,
            created_at=datetime.now(timezone.utc),
            policy=policy,
        )

        mock_db.execute = AsyncMock(
            side_effect=[
                _make_result_scalar_one_or_none(user),        # user lookup
                _make_result_scalar_one_or_none(assignment),   # user assignment (resolve)
                _make_result_scalar_one_or_none(assignment),   # user assignment (source check)
            ]
        )

        resp = await client.get("/admin/api/policies/resolve/owui-resolved")

        assert resp.status_code == 200
        data = resp.json()
        assert data["policy"]["name"] == "user-policy"
        assert data["source"] == "user"


class TestDryRunPolicy:
    """R3: POST /admin/api/policies/{id}/dry-run"""

    @pytest.mark.asyncio
    async def test_not_found(self, client, mock_db):
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(None))

        resp = await client.post(
            f"/admin/api/policies/{uuid.uuid4()}/dry-run",
            json={"sandbox_name": "sg-test-1234"},
        )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.routes.policies.openshell_client")
    async def test_successful_dry_run(self, mock_oc, client, mock_db, make_policy):
        p = make_policy(
            yaml="metadata:\n  name: test\n  tier: restricted\n  version: '1.0'\nnetwork:\n  default: deny\n",
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(p))

        mock_oc.dry_run_policy = AsyncMock(return_value='{"status": "ok", "changes": []}')

        resp = await client.post(
            f"/admin/api/policies/{p.id}/dry-run",
            json={"sandbox_name": "sg-test-1234"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_name"] == "sg-test-1234"
        assert data["result"]["status"] == "ok"

    @pytest.mark.asyncio
    @patch("app.routes.policies.openshell_client")
    async def test_dry_run_openshell_error(self, mock_oc, client, mock_db, make_policy):
        from app.services.openshell_client import OpenShellError

        p = make_policy(
            yaml="metadata:\n  name: test\n  tier: restricted\n  version: '1.0'\nnetwork:\n  default: deny\n",
        )
        mock_db.execute = AsyncMock(return_value=_make_result_scalar_one_or_none(p))

        mock_oc.dry_run_policy = AsyncMock(side_effect=OpenShellError("sandbox unreachable"))
        mock_oc.OpenShellError = OpenShellError

        resp = await client.post(
            f"/admin/api/policies/{p.id}/dry-run",
            json={"sandbox_name": "sg-test-1234"},
        )

        assert resp.status_code == 502

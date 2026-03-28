"""Unit tests for policy engine validation and diff functions."""

import textwrap

from app.services.policy_engine import (
    classify_policy_changes,
    diff_policy_yaml,
    validate_policy_yaml,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_POLICY = textwrap.dedent("""\
    metadata:
      name: test-policy
      tier: standard
      version: "1.0"
    network:
      default: deny
      egress:
        - host: "*.example.com"
          ports: [443]
    filesystem:
      default: deny
      writable:
        - /home/user
        - /tmp
      readable:
        - /usr
    process:
      allow_sudo: false
      allow_ptrace: false
""")


# ===================================================================
# validate_policy_yaml
# ===================================================================


class TestValidatePolicyYaml:
    """Tests for validate_policy_yaml()."""

    def test_valid_policy_all_sections(self):
        is_valid, errors = validate_policy_yaml(_VALID_POLICY)
        assert is_valid is True
        assert errors == []

    def test_valid_policy_network_only(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: net-only
              tier: restricted
              version: "1.0"
            network:
              default: allow
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is True
        assert errors == []

    def test_valid_policy_filesystem_only(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: fs-only
              tier: elevated
              version: "2.0"
            filesystem:
              default: allow
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is True
        assert errors == []

    def test_valid_policy_process_only(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: proc-only
              tier: standard
              version: "1.0"
            process:
              allow_sudo: true
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is True
        assert errors == []

    def test_missing_metadata_section(self):
        yaml_str = textwrap.dedent("""\
            network:
              default: deny
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("metadata" in e.lower() for e in errors)

    def test_metadata_not_a_mapping(self):
        yaml_str = textwrap.dedent("""\
            metadata: "just a string"
            network:
              default: deny
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("metadata" in e.lower() and "mapping" in e.lower() for e in errors)

    def test_missing_metadata_fields(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: incomplete
            network:
              default: deny
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("tier" in e for e in errors)
        assert any("version" in e for e in errors)

    def test_invalid_tier_value(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-tier
              tier: superuser
              version: "1.0"
            network:
              default: deny
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("tier" in e and "superuser" in e for e in errors)

    def test_invalid_yaml_syntax(self):
        yaml_str = "metadata:\n  name: [unterminated"
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("syntax" in e.lower() for e in errors)

    def test_non_dict_yaml(self):
        yaml_str = "- item1\n- item2"
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("mapping" in e.lower() for e in errors)

    def test_no_policy_sections(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: empty
              tier: standard
              version: "1.0"
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("network" in e and "filesystem" in e and "process" in e for e in errors)

    def test_invalid_network_default(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-net
              tier: standard
              version: "1.0"
            network:
              default: block
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("network.default" in e for e in errors)

    def test_network_egress_not_a_list(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-egress
              tier: standard
              version: "1.0"
            network:
              egress: "not-a-list"
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("egress" in e and "list" in e for e in errors)

    def test_network_not_a_mapping(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-net
              tier: standard
              version: "1.0"
            network: "string"
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("network" in e.lower() and "mapping" in e.lower() for e in errors)

    def test_invalid_filesystem_default(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-fs
              tier: standard
              version: "1.0"
            filesystem:
              default: block
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("filesystem.default" in e for e in errors)

    def test_filesystem_writable_not_a_list(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-writable
              tier: standard
              version: "1.0"
            filesystem:
              writable: /single/path
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("writable" in e and "list" in e for e in errors)

    def test_filesystem_writable_non_string_entries(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-entries
              tier: standard
              version: "1.0"
            filesystem:
              writable:
                - 123
                - true
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("writable" in e and "string" in e for e in errors)

    def test_process_allow_sudo_not_boolean(self):
        yaml_str = textwrap.dedent("""\
            metadata:
              name: bad-proc
              tier: standard
              version: "1.0"
            process:
              allow_sudo: "yes"
        """)
        is_valid, errors = validate_policy_yaml(yaml_str)
        assert is_valid is False
        assert any("allow_sudo" in e and "boolean" in e for e in errors)

    def test_empty_string_input(self):
        is_valid, errors = validate_policy_yaml("")
        assert is_valid is False
        assert len(errors) > 0


# ===================================================================
# diff_policy_yaml
# ===================================================================


class TestDiffPolicyYaml:
    """Tests for diff_policy_yaml()."""

    _OLD = textwrap.dedent("""\
        metadata:
          name: base
          tier: standard
          version: "1.0"
        network:
          default: deny
        filesystem:
          default: deny
          writable:
            - /tmp
    """)

    def test_identical_policies(self):
        result = diff_policy_yaml(self._OLD, self._OLD)
        assert result["sections_changed"] == []
        assert result["sections_added"] == []
        assert result["sections_removed"] == []
        assert result["has_dynamic_changes"] is False
        assert result["has_static_changes"] is False
        assert result["metadata_changed"] is False

    def test_added_section(self):
        new = self._OLD + textwrap.dedent("""\
        process:
          allow_sudo: true
        """)
        result = diff_policy_yaml(self._OLD, new)
        assert "process" in result["sections_added"]
        assert result["has_static_changes"] is True

    def test_removed_section(self):
        new = textwrap.dedent("""\
            metadata:
              name: base
              tier: standard
              version: "1.0"
            network:
              default: deny
        """)
        result = diff_policy_yaml(self._OLD, new)
        assert "filesystem" in result["sections_removed"]
        assert result["has_static_changes"] is True

    def test_changed_section(self):
        new = textwrap.dedent("""\
            metadata:
              name: base
              tier: standard
              version: "1.0"
            network:
              default: allow
            filesystem:
              default: deny
              writable:
                - /tmp
        """)
        result = diff_policy_yaml(self._OLD, new)
        assert "network" in result["sections_changed"]
        assert result["has_dynamic_changes"] is True
        assert result["has_static_changes"] is False

    def test_dynamic_section_change_network(self):
        new = textwrap.dedent("""\
            metadata:
              name: base
              tier: standard
              version: "1.0"
            network:
              default: allow
            filesystem:
              default: deny
              writable:
                - /tmp
        """)
        result = diff_policy_yaml(self._OLD, new)
        assert "network" in result["dynamic_sections_changed"]
        assert result["has_dynamic_changes"] is True

    def test_static_section_change_filesystem(self):
        new = textwrap.dedent("""\
            metadata:
              name: base
              tier: standard
              version: "1.0"
            network:
              default: deny
            filesystem:
              default: allow
              writable:
                - /home/user
        """)
        result = diff_policy_yaml(self._OLD, new)
        assert "filesystem" in result["static_sections_changed"]
        assert result["has_static_changes"] is True

    def test_metadata_only_change(self):
        new = textwrap.dedent("""\
            metadata:
              name: renamed
              tier: standard
              version: "2.0"
            network:
              default: deny
            filesystem:
              default: deny
              writable:
                - /tmp
        """)
        result = diff_policy_yaml(self._OLD, new)
        assert result["metadata_changed"] is True
        assert result["has_dynamic_changes"] is False
        assert result["has_static_changes"] is False

    def test_unified_diff_present(self):
        new = self._OLD.replace("deny", "allow")
        result = diff_policy_yaml(self._OLD, new)
        assert result["unified_diff"] != ""
        assert "---" in result["unified_diff"]

    def test_details_contain_old_and_new(self):
        new = textwrap.dedent("""\
            metadata:
              name: base
              tier: standard
              version: "1.0"
            network:
              default: allow
            filesystem:
              default: deny
              writable:
                - /tmp
        """)
        result = diff_policy_yaml(self._OLD, new)
        assert "network" in result["details"]
        assert "old" in result["details"]["network"]
        assert "new" in result["details"]["network"]


# ===================================================================
# classify_policy_changes
# ===================================================================


class TestClassifyPolicyChanges:
    """Tests for classify_policy_changes()."""

    _BASE = textwrap.dedent("""\
        metadata:
          name: test
          tier: standard
          version: "1.0"
        network:
          default: deny
        filesystem:
          default: deny
    """)

    def test_returns_tuple(self):
        result = classify_policy_changes(self._BASE, self._BASE)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_dynamic_change(self):
        new = self._BASE.replace("network:\n  default: deny", "network:\n  default: allow")
        has_dynamic, has_static = classify_policy_changes(self._BASE, new)
        assert has_dynamic is True
        assert has_static is False

    def test_static_change(self):
        new = self._BASE.replace("filesystem:\n  default: deny", "filesystem:\n  default: allow")
        has_dynamic, has_static = classify_policy_changes(self._BASE, new)
        assert has_dynamic is False
        assert has_static is True

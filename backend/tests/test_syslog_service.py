"""Unit tests for the syslog/SIEM forwarding service."""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.syslog_service import (
    SyslogConfig,
    _category_to_severity,
    dispatch_syslog,
    format_rfc5424,
    invalidate_cache,
)


# ---------------------------------------------------------------------------
# RFC 5424 formatting
# ---------------------------------------------------------------------------


class TestFormatRFC5424:
    def test_basic_format(self):
        msg = format_rfc5424(
            facility=1,
            severity=6,
            app_name="shellguard",
            msg_id="test_event",
            structured_data={"shellguard": {"category": "lifecycle", "event_type": "assigned"}},
            message='{"user":"alice"}',
        )
        decoded = msg.decode("utf-8")

        # Should start with PRI (1*8+6 = 14)
        assert decoded.startswith("<14>1 ")
        # Should contain app name
        assert "shellguard" in decoded
        # Should contain msg_id
        assert "test_event" in decoded
        # Should contain structured data
        assert '[shellguard category="lifecycle" event_type="assigned"]' in decoded
        # Should end with message + newline
        assert decoded.strip().endswith('{"user":"alice"}')

    def test_empty_structured_data(self):
        msg = format_rfc5424(
            facility=1, severity=6, app_name="test",
            msg_id="evt", structured_data={}, message="hello",
        )
        decoded = msg.decode("utf-8")
        # Empty SD should be "-"
        assert " - hello" in decoded

    def test_pri_calculation(self):
        """PRI = facility * 8 + severity."""
        # facility=16 (local0), severity=3 (error) → PRI=131
        msg = format_rfc5424(
            facility=16, severity=3, app_name="test",
            msg_id="x", structured_data={}, message="err",
        )
        assert msg.startswith(b"<131>1 ")

    def test_timestamp_format(self):
        msg = format_rfc5424(
            facility=1, severity=6, app_name="test",
            msg_id="x", structured_data={}, message="m",
        )
        decoded = msg.decode("utf-8")
        # Timestamp should be ISO 8601 with Z suffix
        parts = decoded.split(" ")
        ts = parts[1]
        assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z", ts)


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------


class TestSeverityMapping:
    def test_lifecycle_is_info(self):
        assert _category_to_severity("lifecycle") == 6

    def test_enforcement_is_warning(self):
        assert _category_to_severity("enforcement") == 4

    def test_admin_is_notice(self):
        assert _category_to_severity("admin") == 5

    def test_unknown_defaults_to_info(self):
        assert _category_to_severity("unknown") == 6


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------


class TestDispatchSyslog:
    @pytest.mark.asyncio
    async def test_noop_when_no_config(self):
        """dispatch_syslog should silently return when no config exists."""
        with patch("app.services.syslog_service._load_syslog_config", return_value=None):
            # Should not raise
            await dispatch_syslog("lifecycle", "assigned", {}, "2026-01-01T00:00:00Z")

    @pytest.mark.asyncio
    async def test_sends_when_configured(self):
        config = SyslogConfig(host="syslog.local", port=514, protocol="udp")

        with (
            patch("app.services.syslog_service._load_syslog_config", return_value=config),
            patch("app.services.syslog_service._send_message", new_callable=AsyncMock) as mock_send,
        ):
            await dispatch_syslog("lifecycle", "assigned", {"user": "alice"}, "2026-01-01T00:00:00Z")
            mock_send.assert_awaited_once()
            call_args = mock_send.call_args
            assert call_args[0][0] is config
            # The data should be bytes
            assert isinstance(call_args[0][1], bytes)

    @pytest.mark.asyncio
    async def test_formats_message_correctly(self):
        config = SyslogConfig(host="syslog.local", port=514, protocol="udp", app_name="sg")

        captured_data = None

        async def capture_send(cfg, data):
            nonlocal captured_data
            captured_data = data

        with (
            patch("app.services.syslog_service._load_syslog_config", return_value=config),
            patch("app.services.syslog_service._send_message", side_effect=capture_send),
        ):
            await dispatch_syslog("enforcement", "policy_applied", {"sandbox": "sg-1"}, "2026-03-01T00:00:00Z")

        assert captured_data is not None
        decoded = captured_data.decode("utf-8")
        # enforcement → severity 4, facility 1 → PRI = 1*8+4 = 12
        assert decoded.startswith("<12>1 ")
        assert "sg" in decoded  # app_name
        assert "policy_applied" in decoded  # msg_id
        assert '[shellguard category="enforcement"' in decoded


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class TestCache:
    def test_invalidate_cache(self):
        import app.services.syslog_service as ss

        ss._config_cache = (0.0, SyslogConfig(host="x"))
        invalidate_cache()
        assert ss._config_cache is None

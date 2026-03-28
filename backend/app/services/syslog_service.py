"""Syslog/SIEM forwarding service for audit events.

Formats audit events as RFC 5424 structured syslog messages and delivers
them over UDP or TCP.  Configuration is stored in the ``system_config``
table under key ``"syslog"``.
"""

import asyncio
import json
import logging
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from app.database import async_session
from app.models import SystemConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


class SyslogConfig(BaseModel):
    host: str
    port: int = 514
    protocol: str = "udp"  # "udp" or "tcp"
    facility: int = 1  # user-level
    app_name: str = "shellguard"


# ---------------------------------------------------------------------------
# Config cache
# ---------------------------------------------------------------------------

_CACHE_TTL = 30.0
_config_cache: tuple[float, SyslogConfig | None] | None = None


async def _load_syslog_config() -> SyslogConfig | None:
    """Load syslog config from the database with a TTL cache."""
    global _config_cache

    now = time.monotonic()
    if _config_cache is not None:
        cached_at, cached = _config_cache
        if now - cached_at < _CACHE_TTL:
            return cached

    try:
        from sqlalchemy import select

        async with async_session() as db:
            row = (
                await db.execute(
                    select(SystemConfig).where(SystemConfig.key == "syslog")
                )
            ).scalar_one_or_none()

        if row and isinstance(row.value, dict) and row.value.get("host"):
            config = SyslogConfig(**row.value)
        else:
            config = None
    except Exception:
        logger.exception("Failed to load syslog config")
        config = None

    _config_cache = (now, config)
    return config


def invalidate_cache() -> None:
    """Clear the config cache."""
    global _config_cache
    _config_cache = None


# ---------------------------------------------------------------------------
# RFC 5424 formatting
# ---------------------------------------------------------------------------

# Severity mapping: category → syslog severity
_SEVERITY_MAP = {
    "lifecycle": 6,     # informational
    "enforcement": 4,   # warning
    "admin": 5,         # notice
}


def _category_to_severity(category: str) -> int:
    return _SEVERITY_MAP.get(category, 6)


def format_rfc5424(
    facility: int,
    severity: int,
    app_name: str,
    msg_id: str,
    structured_data: dict[str, dict[str, str]],
    message: str,
) -> bytes:
    """Format a message per RFC 5424.

    ``<PRI>VERSION TIMESTAMP HOSTNAME APP-NAME PROCID MSGID [SD] MSG``
    """
    pri = facility * 8 + severity
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    hostname = socket.gethostname()
    procid = str(os.getpid())

    # Build structured data string
    sd_parts = []
    for sd_id, params in structured_data.items():
        param_str = " ".join(
            f'{k}="{v}"' for k, v in params.items()
        )
        sd_parts.append(f"[{sd_id} {param_str}]")
    sd_str = "".join(sd_parts) if sd_parts else "-"

    line = f"<{pri}>1 {timestamp} {hostname} {app_name} {procid} {msg_id} {sd_str} {message}\n"
    return line.encode("utf-8")


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------

_udp_transport: asyncio.DatagramTransport | None = None
_tcp_writer: asyncio.StreamWriter | None = None
_tcp_reader: asyncio.StreamReader | None = None


class _UDPProtocol(asyncio.DatagramProtocol):
    def error_received(self, exc: Exception) -> None:
        logger.debug("Syslog UDP error: %s", exc)

    def connection_lost(self, exc: Exception | None) -> None:
        pass


async def _ensure_udp(config: SyslogConfig) -> asyncio.DatagramTransport | None:
    global _udp_transport
    if _udp_transport is not None:
        return _udp_transport

    try:
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            _UDPProtocol,
            remote_addr=(config.host, config.port),
        )
        _udp_transport = transport
        return transport
    except Exception:
        logger.exception("Failed to create syslog UDP endpoint")
        return None


async def _ensure_tcp(config: SyslogConfig) -> asyncio.StreamWriter | None:
    global _tcp_reader, _tcp_writer
    if _tcp_writer is not None:
        return _tcp_writer

    try:
        reader, writer = await asyncio.open_connection(config.host, config.port)
        _tcp_reader = reader
        _tcp_writer = writer
        return writer
    except Exception:
        logger.exception("Failed to create syslog TCP connection")
        return None


async def _send_message(config: SyslogConfig, data: bytes) -> None:
    """Send a syslog message using the configured transport."""
    if config.protocol == "tcp":
        writer = await _ensure_tcp(config)
        if writer is None:
            return
        try:
            writer.write(data)
            await writer.drain()
        except Exception:
            logger.debug("Syslog TCP send failed — reconnecting", exc_info=True)
            await _close_tcp()
            # Retry once after reconnect
            writer = await _ensure_tcp(config)
            if writer is not None:
                try:
                    writer.write(data)
                    await writer.drain()
                except Exception:
                    logger.warning("Syslog TCP send failed after reconnect")
                    await _close_tcp()
    else:
        transport = await _ensure_udp(config)
        if transport is not None:
            try:
                transport.sendto(data)
            except Exception:
                logger.debug("Syslog UDP send failed", exc_info=True)


async def _close_udp() -> None:
    global _udp_transport
    if _udp_transport is not None:
        _udp_transport.close()
        _udp_transport = None


async def _close_tcp() -> None:
    global _tcp_reader, _tcp_writer
    if _tcp_writer is not None:
        try:
            _tcp_writer.close()
            await _tcp_writer.wait_closed()
        except Exception:
            pass
        _tcp_writer = None
        _tcp_reader = None


# ---------------------------------------------------------------------------
# Dispatch entry point
# ---------------------------------------------------------------------------


async def dispatch_syslog(
    category: str,
    event_type: str,
    details: dict[str, Any],
    timestamp: str,
) -> None:
    """Format and send an audit event via syslog."""
    config = await _load_syslog_config()
    if config is None:
        return

    severity = _category_to_severity(category)
    structured_data = {
        "shellguard": {
            "category": category,
            "event_type": event_type,
            "timestamp": timestamp,
        }
    }
    message = json.dumps(details, default=str)
    packet = format_rfc5424(
        config.facility, severity, config.app_name,
        event_type, structured_data, message,
    )
    await _send_message(config, packet)


# ---------------------------------------------------------------------------
# Service lifecycle
# ---------------------------------------------------------------------------


class SyslogService:
    """Manages syslog transport connections."""

    async def start(self) -> None:
        logger.info("Syslog service started")

    async def stop(self) -> None:
        await _close_udp()
        await _close_tcp()
        invalidate_cache()
        logger.info("Syslog service stopped")


syslog_service = SyslogService()

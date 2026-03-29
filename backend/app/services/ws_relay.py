"""Bidirectional WebSocket relay between a FastAPI client and an upstream server.

Used to relay PTY terminal sessions from admin/user WebSocket endpoints to
the Open Terminal ``/ws/terminal`` endpoint running inside each sandbox.
"""

import asyncio
import logging

from fastapi import WebSocket
from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


async def relay_websocket(
    client_ws: WebSocket,
    target_url: str,
    *,
    extra_headers: dict[str, str] | None = None,
) -> None:
    """Relay data bidirectionally between *client_ws* and *target_url*.

    Opens a WebSocket connection to *target_url* (the sandbox's Open Terminal
    PTY endpoint) and runs two concurrent tasks:

    - **client -> sandbox**: reads from the client and writes to the sandbox.
    - **sandbox -> client**: reads from the sandbox and writes to the client.

    Returns when either side disconnects.
    """
    headers = extra_headers or {}

    try:
        async with ws_connect(target_url, additional_headers=headers) as upstream:
            # If the sandbox's Open Terminal uses first-message auth, the
            # Authorization header we sent in extra_headers handles it.

            async def _client_to_upstream() -> None:
                try:
                    while True:
                        data = await client_ws.receive_bytes()
                        await upstream.send(data)
                except Exception:
                    pass

            async def _upstream_to_client() -> None:
                try:
                    async for message in upstream:
                        if isinstance(message, bytes):
                            await client_ws.send_bytes(message)
                        else:
                            await client_ws.send_text(message)
                except ConnectionClosed:
                    pass
                except Exception:
                    pass

            tasks = [
                asyncio.create_task(_client_to_upstream(), name="ws-c2s"),
                asyncio.create_task(_upstream_to_client(), name="ws-s2c"),
            ]

            # Wait for either direction to finish, then cancel the other.
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    except ConnectionClosed:
        logger.debug("Upstream WebSocket closed for %s", target_url)
    except OSError as exc:
        logger.warning("Cannot connect to upstream WebSocket %s: %s", target_url, exc)
    except Exception:
        logger.exception("WebSocket relay error for %s", target_url)
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass

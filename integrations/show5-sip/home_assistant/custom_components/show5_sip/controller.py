"""Serialized controls with explicit call identity and app acknowledgement."""
from __future__ import annotations

import asyncio
import secrets
import uuid

from .protocol import ProtocolError, control_command, extract_output, foreground_command, parse_status, status_command, validate_endpoint


class Endpoint:
    def __init__(self, config, execute, *, acknowledgement_timeout=12, poll_delay=.5):
        self.config = validate_endpoint(config)
        self.execute = execute
        self.acknowledgement_timeout = acknowledgement_timeout
        self.poll_delay = poll_delay
        self.lock = asyncio.Lock()
        self.status = None

    async def _read(self, context=None):
        marker = secrets.token_hex(16)
        output = await self.execute(status_command(self.config["serial"], marker), context)
        self.status = parse_status(output, marker, self.config["endpoint_id"])
        return self.status

    async def refresh(self):
        async with self.lock:
            return await self._read()

    async def command(self, command, *, contact_id=None, expected_call_id=None, context=None):
        async with self.lock:
            current = await self._read(context)
            if command == "dial":
                if contact_id not in {item["id"] for item in self.config["contacts"]}:
                    raise ProtocolError("contact_not_allowed")
                if not current.configured or current.registration != "registered":
                    raise ProtocolError("not_registered")
                if current.state not in {"idle", "error"} or current.call_id is not None or current.lease_held:
                    raise ProtocolError("endpoint_busy")
            elif command in {"answer", "decline", "hangup"}:
                if not expected_call_id or expected_call_id != current.call_id:
                    raise ProtocolError("call_changed")
                if command in {"answer", "decline"} and current.state != "ringing":
                    raise ProtocolError("not_ringing")
                if command == "hangup" and current.state not in {"ringing", "preparing", "dialing", "active", "ending"}:
                    raise ProtocolError("no_active_call")
            else:
                raise ProtocolError("invalid_command")
            if command in {"dial", "answer"}:
                # Bring explicit operator calls to the foreground before asking for microphone use.
                # Android 11 does not give background-only FGS launches equivalent capture rights.
                marker = secrets.token_hex(16)
                output = extract_output(await self.execute(foreground_command(self.config["serial"], marker), context), marker)
                if "Status: ok" not in output.splitlines() or "Error:" in output or "Exception" in output:
                    raise ProtocolError("foreground_launch_failed")
            command_id, marker = str(uuid.uuid4()), secrets.token_hex(16)
            text = control_command(self.config["serial"], marker, command, command_id=command_id,
                                   contact_id=contact_id, expected_call_id=expected_call_id)
            # Send once. An uncertain response must never cause a second dial.
            response = await self.execute(text, context)
            extract_output(response, marker)
            try:
                async with asyncio.timeout(self.acknowledgement_timeout):
                    while True:
                        result = await self._read(context)
                        if result.last_command_id == command_id:
                            if result.last_command_result == "rejected":
                                raise ProtocolError(result.last_command_error or "command_rejected")
                            return result
                        await asyncio.sleep(self.poll_delay)
            except TimeoutError:
                raise ProtocolError("command_acknowledgement_timeout") from None

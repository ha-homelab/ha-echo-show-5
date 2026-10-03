"""One private video room. HA auth transports signaling; no configured STUN/TURN."""
from __future__ import annotations
import asyncio
import secrets
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import Context
from homeassistant.helpers import config_validation as cv
from . import DOMAIN, backend_for, owner, reply


class Room:
    def __init__(self, hass, backend):
        self.hass, self.backend = hass, backend
        self.peers = {}
        self.call = None
        self.timer = None
        self.lock = asyncio.Lock()

    def emit(self, role, event):
        if role in self.peers:
            connection, message_id, _peer_id = self.peers[role]
            connection.send_event(message_id, event)

    def role(self, connection, peer_id):
        for role, peer in self.peers.items():
            if peer[0] is connection and peer[2] == peer_id:
                return role
        raise ValueError("Join the room first")

    async def leave(self, role, membership):
        async with self.lock:
            if self.peers.get(role) != membership:
                return
            try:
                await self._finish_locked()
            finally:
                if self.peers.get(role) == membership:
                    self.peers.pop(role, None)

    async def finish(self):
        async with self.lock:
            await self._finish_locked()

    async def _finish_locked(self):
        call = self.call
        if self.timer and self.timer is not asyncio.current_task():
            self.timer.cancel()
        self.timer = None
        if call:
            for role in tuple(self.peers):
                self.emit(role, {"event": "ended"})
        if call and call.get("lease"):
            await self.backend.guard.end(call["lease"], call["owner"])
        self.call = None
        if call:
            for role in tuple(self.peers):
                self.emit(role, {"event": "restored"})

    async def expire(self, seconds):
        try:
            await asyncio.sleep(seconds)
            await self.finish()
        except asyncio.CancelledError:
            pass


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/room_join", vol.Required("role"): vol.In(["caller", "show"])})
@websocket_api.async_response
async def join(hass, connection, msg):
    try:
        backend = backend_for(hass, connection)
        if backend.recovery_pending or not (backend.config["video_enabled"] and backend.config.get("adb_entity")):
            raise ValueError("Video mode disabled")
        room, role = backend.room, msg["role"]
        if role in room.peers or any(peer[0] is connection for peer in room.peers.values()):
            raise ValueError("Room role occupied")
        peer_id = secrets.token_hex(16)
        membership = (connection, msg["id"], peer_id)
        room.peers[role] = membership
        connection.subscriptions[msg["id"]] = lambda: hass.async_create_task(room.leave(role, membership))
        connection.send_result(msg["id"])
        room.emit(role, {"event": "joined", "role": role, "peer_id": peer_id})
    except Exception:
        connection.send_error(msg["id"], "room_unavailable", "This private room is unavailable.")


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/room_action", vol.Required("peer_id"): vol.Match(r"^[0-9a-f]{32}$"), vol.Required("action"): vol.In(["call", "accept", "end"])})
@websocket_api.async_response
async def action(hass, connection, msg):
    async def run():
        room = backend_for(hass, connection).room
        async with room.lock:
            role = room.role(connection, msg["peer_id"])
            if msg["action"] == "end":
                await room._finish_locked()
                return {"ended": True}
            if msg["action"] == "call":
                if role != "caller" or room.call or room.backend.guard.active:
                    raise ValueError("Show is not ready")
                if "show" not in room.peers:
                    await room.backend.adb("wake", Context(user_id=connection.user.id))
                    await room.backend.adb("open_calls", Context(user_id=connection.user.id))
                    async with asyncio.timeout(45):
                        while "show" not in room.peers:
                            await asyncio.sleep(.2)
                room.call = {"id": secrets.token_hex(16), "owner": owner(connection), "lease": None, "signals": 0}
                room.emit("show", {"event": "incoming"})
                room.timer = hass.async_create_task(room.expire(30))
                return {"ringing": True}
            if role != "show" or not room.call or room.call["lease"]:
                raise ValueError("No incoming call")
            await room.backend.adb("probe", Context(user_id=connection.user.id))
            lease = await room.backend.guard.acquire(room.call["owner"], "video", seconds=120)
            room.call["lease"] = lease.token
            if room.timer:
                room.timer.cancel()
            room.timer = hass.async_create_task(room.expire(120))
            room.emit("show", {"event": "ready", "call_id": room.call["id"]})
            room.emit("caller", {"event": "ready", "call_id": room.call["id"]})
            return {"accepted": True, "max_seconds": 120}
    await reply(connection, msg, run)


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/signal", vol.Required("kind"): vol.In(["offer", "answer", "candidate"]),
                                vol.Required("peer_id"): vol.Match(r"^[0-9a-f]{32}$"), vol.Required("call_id"): vol.Match(r"^[0-9a-f]{32}$"), vol.Required("data"): dict})
@websocket_api.async_response
async def signal(hass, connection, msg):
    async def run():
        room = backend_for(hass, connection).room
        role = room.role(connection, msg["peer_id"])
        call = room.call
        if not call or not call["lease"] or call["id"] != msg["call_id"]:
            raise ValueError("No active call")
        room.backend.guard.require(call["lease"], call["owner"], "video")
        if call["signals"] >= 150:
            raise ValueError("Signal limit exceeded")
        kind, data = msg["kind"], msg["data"]
        if kind in {"offer", "answer"}:
            if (kind == "offer") != (role == "caller") or set(data) != {"sdp", "type"} or data["type"] != kind or not isinstance(data["sdp"], str) or len(data["sdp"]) > 65536:
                raise ValueError("Invalid session description")
        else:
            if set(data) - {"candidate", "sdpMid", "sdpMLineIndex", "usernameFragment"} or not isinstance(data.get("candidate"), str) or len(data["candidate"]) > 2048:
                raise ValueError("Invalid candidate")
            for key in ("sdpMid", "usernameFragment"):
                if data.get(key) is not None and (not isinstance(data[key], str) or len(data[key]) > 256):
                    raise ValueError("Invalid candidate field")
            if data.get("sdpMLineIndex") is not None and (type(data["sdpMLineIndex"]) is not int or not 0 <= data["sdpMLineIndex"] < 16):
                raise ValueError("Invalid media index")
        call["signals"] += 1
        room.emit("show" if role == "caller" else "caller", {"event": "signal", "kind": kind, "data": data})
        return {"sent": True}
    await reply(connection, msg, run)


def register(hass):
    for command in (join, action, signal):
        websocket_api.async_register_command(hass, command)

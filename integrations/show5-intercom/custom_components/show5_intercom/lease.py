"""Bounded exclusive resource lease. No Home Assistant or network imports."""
from __future__ import annotations

import asyncio
import base64
import binascii
import secrets
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Any

RATE = 44100
MAX_SECONDS = 10
MAX_BYTES = RATE * 2 * MAX_SECONDS


def decode_pcm(value: str) -> bytes:
    """Strict PCM16 mono/44.1k upload, between 20ms and ten seconds."""
    if not isinstance(value, str) or len(value) > (MAX_BYTES + 2) // 3 * 4:
        raise ValueError("Audio exceeds ten seconds")
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as err:
        raise ValueError("Invalid audio encoding") from err
    if not 1764 <= len(data) <= MAX_BYTES or len(data) % 2:
        raise ValueError("Audio must be 20ms–10s PCM16 mono at 44100Hz")
    return data


@dataclass
class Lease:
    token: str
    owner: str
    mode: str
    prior_muted: bool
    deadline: float


class LeaseGuard:
    """One session; failed preparation, timeout and explicit end all restore it.

    Hooks: snapshot() -> bool, prepare(mode), restore(mode, prior_muted),
    journal(dict|None). The journal is saved before any resource mutation.
    A restore error retains the lease/journal and blocks new acquisitions.
    """

    def __init__(self, snapshot, prepare, restore, journal):
        self.snapshot = snapshot
        self.prepare = prepare
        self.restore = restore
        self.journal = journal
        self.active: Lease | None = None
        self.lock = asyncio.Lock()
        self.timer: asyncio.Task | None = None
        self.cleanup_error = False

    async def acquire(self, owner: str, mode: str, seconds: float = 45) -> Lease:
        async with self.lock:
            if self.active:
                raise ValueError("Device is already in a session or needs recovery")
            if mode not in {"talk", "listen", "video", "jitsi"} or not 0 < seconds <= 120:
                raise ValueError("Invalid session")
            prior = await self.snapshot()
            lease = Lease(secrets.token_hex(16), owner, mode, prior, time.monotonic() + seconds)
            await self.journal({"mode": mode, "prior_muted": prior})
            self.active = lease
            try:
                async with asyncio.timeout_at(lease.deadline):
                    await self.prepare(mode)
            except BaseException:
                await self._restore_locked()
                raise
            self.timer = asyncio.create_task(self._expire(lease))
            return lease

    def require(self, token: str, owner: str, mode: str | None = None) -> Lease:
        lease = self.active
        if lease is None or lease.token != token or lease.owner != owner:
            raise ValueError("Session not owned by this connection")
        if mode and lease.mode != mode:
            raise ValueError("Wrong session mode")
        if time.monotonic() >= lease.deadline:
            raise ValueError("Session expired")
        return lease

    async def perform(self, token: str, owner: str, mode: str, action: Callable[[], Awaitable[Any]]):
        async with self.lock:
            lease = self.require(token, owner, mode)
            try:
                async with asyncio.timeout_at(lease.deadline):
                    return await action()
            finally:
                # Upload/listen are single-shot. Every outcome restores ownership.
                await self._restore_locked()

    async def end(self, token: str, owner: str):
        async with self.lock:
            lease = self.active
            if lease is None:
                return
            if lease.token != token or lease.owner != owner:
                raise ValueError("Session not owned by this connection")
            await self._restore_locked()

    async def recover(self, record: dict):
        async with self.lock:
            if record.get("mode") not in {"talk", "listen", "video", "jitsi"} or type(record.get("prior_muted")) is not bool:
                raise ValueError("Invalid recovery journal")
            self.active = Lease(secrets.token_hex(16), "recovery", record["mode"], record["prior_muted"], 0)
            await self._restore_locked()

    async def _expire(self, lease: Lease):
        try:
            await asyncio.sleep(max(0, lease.deadline - time.monotonic()))
            async with self.lock:
                if self.active is lease:
                    await self._restore_locked()
        except asyncio.CancelledError:
            pass
        except Exception:
            # The restore hook reports operator-visible failure. Retain the
            # journal/lease and allow explicit guarded recovery.
            self.cleanup_error = True

    async def _restore_locked(self):
        lease = self.active
        if lease is None:
            return
        try:
            await self.restore(lease.mode, lease.prior_muted)
            await self.journal(None)
        except BaseException:
            self.cleanup_error = True
            raise
        self.active = None
        self.cleanup_error = False
        if self.timer and self.timer is not asyncio.current_task():
            self.timer.cancel()
        self.timer = None

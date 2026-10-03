"""Offline lifecycle tests. Does not import HA, contact hosts or use microphones."""
import asyncio
import base64
import importlib.util
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("show5_lease", ROOT / "custom_components/show5_intercom/lease.py")
lease = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lease
spec.loader.exec_module(lease)


class Fake:
    def __init__(self, prior=False):
        self.prior = prior
        self.muted = prior
        self.events = []
        self.record = None
        self.fail_prepare = False
        self.fail_restore = False
        self.guard = lease.LeaseGuard(self.snapshot, self.prepare, self.restore, self.journal)
    async def snapshot(self): return self.prior
    async def journal(self, record): self.record = record; self.events.append(("journal", record))
    async def prepare(self, mode):
        self.events.append(("prepare", mode)); self.muted = True
        if self.fail_prepare: raise RuntimeError("prepare failed")
    async def restore(self, mode, muted):
        self.events.append(("restore", mode, muted))
        if self.fail_restore: raise RuntimeError("restore failed")
        self.muted = muted


class PCMTests(unittest.TestCase):
    def test_valid_boundaries(self):
        for length in (1764, 882000):
            pcm=b"\0"*length
            self.assertEqual(lease.decode_pcm(base64.b64encode(pcm).decode()), pcm)
    def test_reject_oversized(self):
        with self.assertRaises(ValueError): lease.decode_pcm(base64.b64encode(b"\0"*882002).decode())
    def test_reject_too_short(self):
        with self.assertRaises(ValueError): lease.decode_pcm("AAAA")
    def test_reject_odd_bytes(self):
        with self.assertRaises(ValueError): lease.decode_pcm(base64.b64encode(b"\0"*1765).decode())
    def test_reject_non_base64(self):
        for value in ("!"*2400, "\n"*2400, None):
            with self.assertRaises(ValueError): lease.decode_pcm(value)


class LeaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_saved_before_mutation(self):
        f=Fake();l=await f.guard.acquire("one","talk")
        self.assertEqual(f.events[0],("journal",{"mode":"talk","prior_muted":False}))
        self.assertTrue(f.muted)
        await f.guard.end(l.token,"one")
        self.assertFalse(f.muted);self.assertIsNone(f.record)
    async def test_preserve_prior_mute(self):
        f=Fake(True);l=await f.guard.acquire("one","talk")
        await f.guard.end(l.token,"one")
        self.assertTrue(f.muted)
    async def test_exclusive(self):
        f=Fake();l=await f.guard.acquire("one","talk")
        with self.assertRaises(ValueError):await f.guard.acquire("two","talk")
        await f.guard.end(l.token,"one")
    async def test_cross_connection_cannot_end(self):
        f=Fake();l=await f.guard.acquire("one","talk")
        with self.assertRaises(ValueError):await f.guard.end(l.token,"two")
        self.assertTrue(f.muted)
        await f.guard.end(l.token,"one")
    async def test_mode_and_token_guard(self):
        f=Fake();l=await f.guard.acquire("one","talk")
        with self.assertRaises(ValueError):f.guard.require(l.token,"one","listen")
        with self.assertRaises(ValueError):f.guard.require("wrong","one")
        await f.guard.end(l.token,"one")
    async def test_failed_prepare_restores(self):
        f=Fake();f.fail_prepare=True
        with self.assertRaises(RuntimeError):await f.guard.acquire("one","listen")
        self.assertIsNone(f.guard.active);self.assertFalse(f.muted)
    async def test_expiry_restores(self):
        f=Fake();await f.guard.acquire("one","talk",.02)
        await asyncio.sleep(.04)
        self.assertIsNone(f.guard.active);self.assertFalse(f.muted)
    async def test_action_failure_restores(self):
        f=Fake();l=await f.guard.acquire("one","talk")
        async def action():raise RuntimeError("network failed")
        with self.assertRaises(RuntimeError):await f.guard.perform(l.token,"one","talk",action)
        self.assertFalse(f.muted);self.assertIsNone(f.guard.active)
    async def test_action_timeout_restores(self):
        f=Fake();l=await f.guard.acquire("one","talk",.02)
        async def action():await asyncio.sleep(2)
        with self.assertRaises(TimeoutError):await f.guard.perform(l.token,"one","talk",action)
        self.assertFalse(f.muted);self.assertIsNone(f.guard.active)
    async def test_action_cancellation_restores(self):
        f=Fake();l=await f.guard.acquire("one","talk")
        started=asyncio.Event()
        async def action():started.set();await asyncio.sleep(2)
        task=asyncio.create_task(f.guard.perform(l.token,"one","talk",action));await started.wait();task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertFalse(f.muted);self.assertIsNone(f.guard.active)
    async def test_restart_recovery(self):
        f=Fake();await f.guard.recover({"mode":"video","prior_muted":True})
        self.assertTrue(f.muted);self.assertIsNone(f.record)
    async def test_restore_error_blocks_new_session_and_retains_journal(self):
        f=Fake();l=await f.guard.acquire("one","talk");f.fail_restore=True
        with self.assertRaises(RuntimeError):await f.guard.end(l.token,"one")
        self.assertTrue(f.guard.cleanup_error);self.assertIsNotNone(f.record)
        with self.assertRaises(ValueError):await f.guard.acquire("two","talk")
        f.fail_restore=False;await f.guard.end(l.token,"one")
        self.assertFalse(f.guard.cleanup_error)
    async def test_reject_invalid_recovery(self):
        f=Fake()
        with self.assertRaises(ValueError):await f.guard.recover({"mode":"listen","prior_muted":"false"})


if __name__ == "__main__":unittest.main()

"""Quiet functional tests: fake transport/decoder only, no HA or device contact."""
import asyncio
import copy
import importlib.util
from pathlib import Path
import unittest

SRC = Path(__file__).resolve().parents[1] / 'src' / 'guarded_announce_core.py'
spec = importlib.util.spec_from_file_location('guarded_core', SRC)
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
ID = 'announce-' + 'a' * 32 + '-225'
ID2 = 'announce-' + 'b' * 32 + '-225'
ENTITY = 'assist_satellite.test'
OWNER = 'owner'
MEDIA = '/api/tts_proxy/prepared.wav'

class Adapter:
    def __init__(self):
        self.calls = []
        self.generation = 0
        self.reason = ''
        self.music_playing = False
        self.caps = dict(protocol=core.PROTOCOL, **{key: True for key in core.CAPABILITIES})
        self.claim_reply = {'status': 'accepted', 'deduplicated': False}
        self.cancel_reply = {'status': 'stopped', 'reason': 'cancelled'}
        self.status_reply = {'status': 'playing'}
        self.pcm = b'\0\0' * 300
        self.decode_error = None
        self.block_decode = None
        self.manager = None
        self.autocomplete = True
    def validate_media(self, media):
        if media != MEDIA:
            raise core.AnnouncementError('unapproved_media_origin')
    def busy_reason(self, policy='skip'):
        return self.reason or ('media_busy' if self.music_playing and policy != 'duck_music' else '')
    async def capabilities(self):
        self.calls.append(('capabilities',))
        return self.caps
    async def decode(self, media):
        self.calls.append(('decode',))
        if self.block_decode:
            await self.block_decode.wait()
        if self.decode_error:
            raise self.decode_error
        return self.pcm
    async def rpc(self, op, request_id, **data):
        self.calls.append((op, request_id, data))
        reply = {'claim': self.claim_reply, 'cancel': self.cancel_reply, 'status': self.status_reply}[op]
        if isinstance(reply, Exception):
            raise reply
        return dict(request_id=request_id, op=op, **reply)
    async def send(self, op, request_id, **data):
        self.calls.append((op, request_id, data))
        if op == 'audio-stop' and self.autocomplete:
            await self.manager.receipt(ENTITY, {'request_id': request_id, 'op': 'event', 'status': 'completed', 'busy_policy': self.manager.records[self.manager.key(ENTITY, request_id)].get('busy_policy', 'skip')})

class ManagerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.saved = []
        async def save(records):
            self.saved.append(copy.deepcopy(records))
        self.manager = core.AnnouncementManager(save, clock=lambda: 1000)
        self.adapter = Adapter()
        self.adapter.manager = self.manager
        self.manager.adapters[ENTITY] = self.adapter
    async def asyncTearDown(self):
        for task in list(self.manager.tasks.values()):
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
    def data(self, **kwargs):
        return dict(request_id=ID, media_id=MEDIA, expires_at=1180, preannounce=False, busy_policy='skip', **kwargs)
    async def submit(self, data=None):
        return await self.manager.submit(ENTITY, OWNER, data or self.data())
    async def finish(self):
        await asyncio.sleep(0)
        await asyncio.gather(*list(self.manager.tasks.values()))
    async def test_enqueue_returns_before_decode_or_native_send(self):
        response = await self.submit()
        self.assertEqual(response['status'], 'accepted')
        self.assertEqual(self.adapter.calls, [])
        self.assertEqual(len(self.saved), 1)
        self.assertNotIn(MEDIA, repr(self.saved))
    async def test_completed_requires_correlated_native_receipt(self):
        await self.submit(); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'completed')
        self.assertEqual([call[0] for call in self.adapter.calls], ['capabilities', 'decode', 'claim', 'audio-start', 'audio-chunk', 'audio-stop'])
    async def test_duplicate_does_not_send_twice(self):
        await self.submit(); await self.finish()
        count = len(self.adapter.calls)
        self.assertEqual((await self.submit())['status'], 'completed')
        self.assertEqual(len(self.adapter.calls), count)
    async def test_conflicting_expiry_and_owner_rejected(self):
        await self.submit()
        with self.assertRaisesRegex(core.AnnouncementError, 'request_conflict'):
            await self.manager.submit(ENTITY, OWNER, dict(self.data(), expires_at=1190))
        with self.assertRaisesRegex(core.AnnouncementError, 'request_conflict'):
            await self.manager.submit(ENTITY, 'other', self.data())
    async def test_restart_preserves_unknown_without_replay(self):
        await self.submit()
        restored = core.AnnouncementManager(self.manager.save, clock=lambda: 1000, records=copy.deepcopy(self.saved[-1]))
        restored.adapters[ENTITY] = self.adapter
        self.assertEqual((await restored.submit(ENTITY, OWNER, self.data()))['status'], 'unknown')
        self.assertEqual(self.adapter.calls, [])
    async def test_busy_is_skipped_without_capability_decode_or_claim(self):
        self.adapter.reason = 'sip_busy'
        self.assertEqual((await self.submit())['status'], 'skipped')
        self.assertEqual(self.adapter.calls, [])
    async def test_second_job_while_busy_is_skipped(self):
        await self.submit()
        self.assertEqual((await self.submit(dict(self.data(), request_id=ID2)))['status'], 'skipped')
    async def test_unsupported_never_decodes_or_falls_back(self):
        self.adapter.caps['atomic_idle_guard'] = False
        await self.submit(); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'skipped')
        self.assertEqual([c[0] for c in self.adapter.calls], ['capabilities'])
    async def test_empty_and_invalid_audio_fail_before_claim(self):
        for pcm in [b'', b'1', b'0' * (core.MAX_PCM_BYTES + 2)]:
            with self.subTest(size=len(pcm)):
                self.manager.records.clear(); self.adapter.calls.clear(); self.adapter.pcm = pcm
                await self.submit(); await self.finish()
                self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'failed')
                self.assertNotIn('claim', [c[0] for c in self.adapter.calls])
    async def test_decode_failure_never_claims(self):
        self.adapter.decode_error = core.AnnouncementError('decode_failed')
        await self.submit(); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'failed')
        self.assertNotIn('claim', [c[0] for c in self.adapter.calls])
    async def test_lost_claim_ack_is_unknown_and_not_retried(self):
        self.adapter.claim_reply = TimeoutError()
        self.adapter.status_reply = {'status': 'unknown'}
        await self.submit(); await self.finish()
        await self.submit()
        self.assertEqual(self.manager.records[self.manager.key(ENTITY, ID)]['status'], 'unknown')
        self.assertEqual([c[0] for c in self.adapter.calls].count('claim'), 1)
        self.assertNotIn('audio-start', [c[0] for c in self.adapter.calls])
    async def test_owned_stop_before_decode_does_not_touch_native(self):
        self.adapter.block_decode = asyncio.Event()
        await self.submit(); await asyncio.sleep(0)
        self.assertEqual((await self.manager.stop(ENTITY, OWNER, ID))['status'], 'stopped')
        self.assertNotIn('cancel', [c[0] for c in self.adapter.calls])
    async def test_wrong_owner_and_unknown_stop_never_send(self):
        await self.submit()
        with self.assertRaisesRegex(core.AnnouncementError, 'request_not_owned'):
            await self.manager.stop(ENTITY, 'other', ID)
        self.assertEqual((await self.manager.stop(ENTITY, OWNER, ID2))['status'], 'unknown')
        self.assertEqual((await self.manager.status(ENTITY, ID2))['status'], 'unknown')
        self.assertEqual(self.adapter.calls, [])
    async def test_late_wrong_id_and_legacy_played_ignored(self):
        await self.submit()
        await self.manager.receipt(ENTITY, {'request_id': ID2, 'status': 'completed', 'op': 'event'})
        await self.manager.receipt(ENTITY, {'status': 'completed'})
        self.assertEqual(self.manager.records[self.manager.key(ENTITY, ID)]['status'], 'accepted')
    async def test_busy_change_after_decode_prevents_claim(self):
        block = self.adapter.block_decode = asyncio.Event()
        await self.submit(); await asyncio.sleep(0)
        self.adapter.reason = 'intercom_busy'; block.set()
        await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'skipped')
        self.assertNotIn('claim', [c[0] for c in self.adapter.calls])
    async def test_expiry_and_policy_validation(self):
        for change in [{'expires_at': 1000}, {'expires_at': 1301}, {'preannounce': True}, {'busy_policy': 'interrupt'}, {'expires_at': True}]:
            with self.subTest(change=change), self.assertRaises(core.AnnouncementError):
                await self.submit(dict(self.data(), **change))
        self.assertEqual(self.adapter.calls, [])

    async def test_stale_disconnect_does_not_cancel_new_generation(self):
        self.adapter.block_decode = asyncio.Event()
        await self.submit(); await asyncio.sleep(0)
        await self.manager.set_status(self.manager.key(ENTITY, ID), 'unknown', 'test_disconnect')
        self.adapter.generation = 1
        await self.submit(dict(self.data(), request_id=ID2)); await asyncio.sleep(0)
        await self.manager.connection_lost(ENTITY, self.adapter, 0)
        key = self.manager.key(ENTITY, ID2)
        self.assertEqual(self.manager.records[key]['status'], 'accepted')
        self.assertFalse(self.manager.tasks[key].done())

    async def test_old_adapter_removal_cannot_unregister_replacement(self):
        replacement = Adapter()
        self.manager.adapters[ENTITY] = replacement
        await self.manager.detach(ENTITY, self.adapter)
        self.assertIs(self.manager.adapters[ENTITY], replacement)

    async def test_terminal_receipt_between_claim_reply_and_persist_is_preserved(self):
        original = self.adapter.rpc
        async def rpc(op, request_id, **data):
            if op == 'claim':
                await self.manager.receipt(ENTITY, {'request_id': request_id, 'op': 'event', 'status': 'failed', 'reason': 'device_failed'})
            return await original(op, request_id, **data)
        self.adapter.rpc = rpc
        await self.submit(); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'failed')
        self.assertNotIn('audio-start', [c[0] for c in self.adapter.calls])

    async def test_unconfirmed_stop_never_returns_stopped(self):
        self.adapter.autocomplete = False
        self.adapter.cancel_reply = TimeoutError()
        await self.submit(); await asyncio.sleep(0)
        result = await self.manager.stop(ENTITY, OWNER, ID)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual([c[1] for c in self.adapter.calls if c[0] == 'cancel'], [ID])

    async def test_native_duplicate_is_polled_without_audio_replay(self):
        self.adapter.claim_reply = {'status': 'accepted', 'deduplicated': True}
        self.adapter.status_reply = {'status': 'completed', 'reason': 'drained'}
        await self.submit(); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'completed')
        self.assertNotIn('audio-start', [c[0] for c in self.adapter.calls])
        self.assertIn('status', [c[0] for c in self.adapter.calls])

    async def test_missing_native_dedup_field_never_streams(self):
        self.adapter.claim_reply = {'status': 'accepted'}
        await self.submit(); await self.finish()
        self.assertEqual(self.manager.records[self.manager.key(ENTITY, ID)]['status'], 'unknown')
        self.assertNotIn('audio-start', [c[0] for c in self.adapter.calls])

    def enable_duck(self):
        self.adapter.caps.update(duck_music=True, duck_music_player='vaca', duck_music_scope='owned_player')
        self.adapter.claim_reply['busy_policy'] = 'duck_music'
        self.adapter.cancel_reply['busy_policy'] = 'duck_music'
        self.adapter.status_reply['busy_policy'] = 'duck_music'

    async def test_default_skip_still_rejects_music_without_dispatch(self):
        self.adapter.music_playing = True
        data = self.data(); data.pop('busy_policy')
        result = await self.submit(data)
        self.assertEqual(result['status'], 'skipped')
        self.assertEqual(result['reason'], 'media_busy')
        self.assertEqual(self.adapter.calls, [])

    async def test_duck_requires_exact_native_capability_without_fallback(self):
        variants = [{}, {'duck_music': False}, {'duck_music': 'true'},
                    {'duck_music': True, 'duck_music_player': 'sendspin', 'duck_music_scope': 'owned_player'},
                    {'duck_music': True, 'duck_music_player': 'vaca', 'duck_music_scope': 'global_volume'}]
        for fields in variants:
            with self.subTest(fields=fields):
                self.manager.records.clear(); self.adapter.calls.clear()
                self.adapter.caps = dict(protocol=core.PROTOCOL, **{key: True for key in core.CAPABILITIES}, **fields)
                await self.submit(dict(self.data(), busy_policy='duck_music')); await self.finish()
                receipt = await self.manager.status(ENTITY, ID)
                self.assertEqual(receipt['status'], 'skipped')
                self.assertEqual(receipt['reason'], 'duck_music_unavailable')
                self.assertEqual([call[0] for call in self.adapter.calls], ['capabilities'])

    async def test_duck_keeps_all_five_guarantees_required(self):
        self.enable_duck(); self.adapter.caps['owned_cancel'] = False
        await self.submit(dict(self.data(), busy_policy='duck_music')); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'skipped')
        self.assertNotIn('claim', [call[0] for call in self.adapter.calls])

    async def test_duck_claim_binds_policy_and_has_no_duplicate_replay(self):
        self.enable_duck(); self.adapter.music_playing = True
        data = dict(self.data(), busy_policy='duck_music')
        await self.submit(data); await self.finish()
        claim = next(call for call in self.adapter.calls if call[0] == 'claim')
        self.assertEqual(claim[2]['busy_policy'], 'duck_music')
        self.assertEqual(claim[2]['payload_fingerprint'], core.media_fingerprint(MEDIA, 'duck_music'))
        self.assertNotEqual(claim[2]['payload_fingerprint'], core.media_fingerprint(MEDIA))
        count = len(self.adapter.calls)
        self.assertEqual((await self.submit(data))['status'], 'completed')
        self.assertEqual(len(self.adapter.calls), count)
        with self.assertRaisesRegex(core.AnnouncementError, 'request_conflict'):
            await self.submit(self.data())

    async def test_old_skip_receipt_and_hashes_remain_compatible(self):
        expected = '2b256f1e1e474ae3693f7e6f196a41b0fed5f8d0388d9bd957949e657ad1a150'
        self.assertEqual(core.digest(MEDIA, 1180.0), expected)
        self.assertEqual(core.digest(MEDIA, 1180.0, 'skip'), expected)
        self.assertEqual(core.media_fingerprint(MEDIA), 'ef9528b8c4830d4255c8b145d6968a7b0c718770e6c7c7f577d8eb89df158a79')
        self.manager.records[self.manager.key(ENTITY, ID)] = dict(entity_id=ENTITY, request_id=ID,
            owner=OWNER, fingerprint=expected, expires_at=1180.0, status='unknown', reason='legacy_receipt', claimed=True, claim_sent=True)
        self.assertEqual((await self.submit(self.data()))['status'], 'unknown')
        data = self.data(); data.pop('busy_policy')
        self.assertEqual((await self.submit(data))['status'], 'unknown')
        with self.assertRaisesRegex(core.AnnouncementError, 'request_conflict'):
            await self.submit(dict(data, busy_policy='duck_music'))
        self.assertEqual(self.adapter.calls, [])

    async def test_skip_wire_shape_unchanged(self):
        await self.submit(); await self.finish()
        claim = next(call for call in self.adapter.calls if call[0] == 'claim')
        self.assertNotIn('busy_policy', claim[2])
        self.assertEqual(claim[2]['payload_fingerprint'], 'ef9528b8c4830d4255c8b145d6968a7b0c718770e6c7c7f577d8eb89df158a79')

    async def test_skipped_request_cannot_change_to_duck(self):
        self.adapter.reason = 'sip_busy'
        self.assertEqual((await self.submit())['status'], 'skipped')
        with self.assertRaisesRegex(core.AnnouncementError, 'request_conflict'):
            await self.submit(dict(self.data(), busy_policy='duck_music'))

    async def test_native_duck_rejection_never_falls_back_to_skip(self):
        self.enable_duck()
        self.adapter.claim_reply = {'status': 'skipped', 'reason': 'unsupported_music'}
        await self.submit(dict(self.data(), busy_policy='duck_music')); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'skipped')
        self.assertEqual([call[0] for call in self.adapter.calls].count('claim'), 1)
        self.assertNotIn('audio-start', [call[0] for call in self.adapter.calls])

    async def test_invalid_policy_types_and_values_are_rejected(self):
        for policy in [None, True, [], {}, '', 'interrupt', 'duck']:
            with self.subTest(policy=policy), self.assertRaises(core.AnnouncementError):
                await self.submit(dict(self.data(), busy_policy=policy))
        self.assertEqual(self.adapter.calls, [])

    async def test_duck_missing_or_wrong_policy_ack_never_streams(self):
        self.enable_duck()
        for echo in [None, 'skip', True]:
            with self.subTest(echo=echo):
                self.manager.records.clear(); self.adapter.calls.clear()
                self.adapter.claim_reply['busy_policy'] = echo
                await self.submit(dict(self.data(), busy_policy='duck_music')); await self.finish()
                record = self.manager.records[self.manager.key(ENTITY, ID)]
                self.assertEqual((record['status'], record['reason']), ('unknown', 'invalid_policy_receipt'))
                self.assertNotIn('audio-start', [call[0] for call in self.adapter.calls])
                self.assertEqual([call[1] for call in self.adapter.calls if call[0] == 'cancel'], [ID])

    async def test_duck_native_duplicate_is_polled_without_restream(self):
        self.enable_duck()
        self.adapter.claim_reply['deduplicated'] = True
        self.adapter.status_reply.update(status='completed', reason='drained')
        await self.submit(dict(self.data(), busy_policy='duck_music')); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'completed')
        self.assertNotIn('audio-start', [call[0] for call in self.adapter.calls])
        self.assertEqual([call[0] for call in self.adapter.calls].count('claim'), 1)

    async def test_duck_terminal_claim_needs_matching_policy_proof(self):
        self.enable_duck()
        for status in ['completed', 'stopped']:
            for echo in [None, 'skip']:
                with self.subTest(status=status, echo=echo):
                    self.manager.records.clear(); self.adapter.calls.clear()
                    self.adapter.claim_reply = dict(status=status, busy_policy=echo)
                    await self.submit(dict(self.data(), busy_policy='duck_music')); await self.finish()
                    record = self.manager.records[self.manager.key(ENTITY, ID)]
                    self.assertEqual((record['status'], record['reason']), ('unknown', 'invalid_policy_receipt'))
                    self.assertNotIn('audio-start', [call[0] for call in self.adapter.calls])
                    self.assertEqual([call[1] for call in self.adapter.calls if call[0] == 'cancel'], [ID])

    async def test_duck_matching_terminal_claim_never_replays_audio(self):
        self.enable_duck()
        self.adapter.claim_reply = dict(status='completed', busy_policy='duck_music')
        await self.submit(dict(self.data(), busy_policy='duck_music')); await self.finish()
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'completed')
        self.assertNotIn('audio-start', [call[0] for call in self.adapter.calls])
        self.assertNotIn('cancel', [call[0] for call in self.adapter.calls])

    async def test_duck_completion_and_stop_require_matching_policy(self):
        self.enable_duck(); self.adapter.autocomplete = False
        await self.submit(dict(self.data(), busy_policy='duck_music')); await asyncio.sleep(0)
        key = self.manager.key(ENTITY, ID)
        self.assertTrue(self.manager.records[key]['claimed'])
        await self.manager.receipt(ENTITY, dict(request_id=ID, op='event', status='completed'))
        self.adapter.status_reply = dict(status='completed', busy_policy='skip')
        self.assertEqual((await self.manager.status(ENTITY, ID))['status'], 'accepted')
        self.adapter.cancel_reply = dict(status='stopped')
        stopped = await self.manager.stop(ENTITY, OWNER, ID)
        self.assertEqual((stopped['status'], stopped['reason']), ('unknown', 'invalid_policy_receipt'))
        self.assertEqual([call[1] for call in self.adapter.calls if call[0] == 'cancel'], [ID])
        await self.manager.receipt(ENTITY, dict(request_id=ID, op='event', status='stopped', busy_policy='duck_music'))
        self.assertEqual(self.manager.records[key]['status'], 'stopped')

    async def test_duck_aborts_only_owned_job_if_call_guard_becomes_busy(self):
        self.enable_duck(); self.adapter.music_playing = True; self.adapter.autocomplete = False
        await self.submit(dict(self.data(), busy_policy='duck_music')); await asyncio.sleep(0)
        self.assertIn('audio-stop', [call[0] for call in self.adapter.calls])
        self.adapter.reason = 'sip_busy'
        await self.finish()
        record = self.manager.records[self.manager.key(ENTITY, ID)]
        self.assertEqual((record['status'], record['reason']), ('unknown', 'sip_busy'))
        self.assertEqual([call[1] for call in self.adapter.calls if call[0] == 'cancel'], [ID])

if __name__ == '__main__':
    unittest.main()

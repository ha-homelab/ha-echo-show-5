"""Offline HA switching checks; no aiohttp dependency, live HA or credentials."""
import copy
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import voice_pipeline as voice


def fixture():
    pipelines = []
    states = {}
    for backend in ('homeway', 'fcc', 'other'):
        pipeline = {'id': backend + '-id', 'name': backend.title()}
        for field, domain in voice.ENGINE_FIELDS.items():
            entity = domain + '.' + backend
            pipeline[field] = entity
            states[entity] = {'state': 'unknown'}
        pipelines.append(pipeline)
    for entity in ('select.show_one', 'select.show_two', 'select.dot'):
        states[entity] = {'state': 'Homeway', 'last_updated': 'revision-0',
                         'context': {'id': 'context-0'},
                         'attributes': {'options': ['preferred', 'Homeway', 'Fcc', 'Other']}}
    return {'pipelines': pipelines, 'preferred': 'homeway-id', 'states': states}


def mapping():
    return {'version': 1, 'backends': {
        'homeway': {'pipeline': {'name': 'Homeway'}},
        'fcc': {'pipeline': {'id': 'fcc-id'}}},
        'assistant_selects': ['select.show_one', 'select.show_two', 'select.dot']}


class FakeHA:
    origin = 'a' * 64

    def __init__(self, data=None):
        self.data = data or fixture()
        self.writes = []
        self.revision = 0
        self.fail_write = None
        self.before_inventory = None
        self.after_write = None

    async def inventory(self):
        if self.before_inventory:
            self.before_inventory(self)
        return copy.deepcopy(self.data)

    def external_change(self, entity, value):
        self.revision += 1
        row = self.data['states'][entity]
        row['state'] = value
        row['last_updated'] = 'revision-' + str(self.revision)
        row['context'] = {'id': 'context-' + str(self.revision)}

    async def write(self, change, value):
        self.writes.append((change.get('entity_id', 'preferred'), value))
        if len(self.writes) == self.fail_write:
            raise RuntimeError('secret server error https://private.invalid/?token=SECRET')
        if change['kind'] == 'preferred':
            self.data['preferred'] = value
        else:
            self.external_change(change['entity_id'], value)
        if self.after_write:
            self.after_write(self)


class VoicePipelineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.patch = mock.patch.object(voice, 'ROOT', self.root)
        self.patch.start()
        self.snapshot = self.root / 'private' / 'snapshot.json'
        self.ha = FakeHA()
        self.mapping = mapping()

    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()

    def journal(self):
        return json.loads(self.snapshot.read_text())

    async def switch(self, backend='fcc', include_default=False):
        changes = voice.plan_switch(await self.ha.inventory(), self.mapping, backend, include_default)
        return await voice.execute(self.ha, changes, self.snapshot)

    def test_mapping_is_explicit_and_rejects_examples_duplicates_and_extra_fields(self):
        self.assertEqual(voice.load_mapping(self.mapping), self.mapping)
        bad = copy.deepcopy(self.mapping)
        bad['assistant_selects'].append(bad['assistant_selects'][0])
        with self.assertRaisesRegex(voice.SafeError, 'duplicate'):
            voice.load_mapping(bad)
        example = json.loads((Path(__file__).resolve().parents[1] /
            'templates/home-assistant/voice-backends.example.json').read_text())
        with self.assertRaises(voice.SafeError):
            voice.load_mapping(example)
        bad = copy.deepcopy(self.mapping)
        bad['backends']['fcc']['pipeline']['name'] = 'Fcc'
        with self.assertRaisesRegex(voice.SafeError, 'exact_id_or_name'):
            voice.load_mapping(bad)
        self.mapping['change_default'] = True
        with self.assertRaisesRegex(voice.SafeError, 'invalid_mapping'):
            voice.load_mapping(self.mapping)

    async def test_all_selectors_switch_and_global_default_is_untouched(self):
        result = await self.switch()
        self.assertTrue(result['applied'])
        self.assertEqual(self.ha.data['preferred'], 'homeway-id')
        self.assertEqual(len(self.ha.writes), 3)
        self.assertTrue(all(row['status'] == 'applied' for row in self.journal()['changes']))
        self.assertEqual(self.snapshot.stat().st_mode & 0o777, 0o600)

    async def test_snapshot_exists_before_first_write_and_contains_no_auth_or_server_data(self):
        seen = []
        self.ha.after_write = lambda client: seen.append(self.journal()['changes'][0]['status'])
        self.ha.data['states']['select.show_one']['attributes']['token'] = 'SECRET'
        with mock.patch.dict(os.environ, {'HA_TOKEN': 'SECRET', 'HA_URL': 'https://private.invalid'}):
            await self.switch()
        self.assertEqual(seen[0], 'write_pending')
        raw = self.snapshot.read_text()
        self.assertNotIn('SECRET', raw)
        self.assertNotIn('private.invalid', raw)
        self.assertNotIn('attributes', raw)

    async def test_idempotent_switch_does_not_write_or_create_snapshot(self):
        result = await self.switch('homeway')
        self.assertTrue(result['noop'])
        self.assertEqual(self.ha.writes, [])
        self.assertFalse(self.snapshot.exists())

    async def test_preflight_checks_every_selector_before_any_write(self):
        self.ha.data['states']['select.dot']['attributes']['options'].remove('Fcc')
        with self.assertRaisesRegex(voice.SafeError, 'target_not_in_assistant_options'):
            await self.switch()
        self.assertEqual(self.ha.writes, [])
        self.assertFalse(self.snapshot.exists())

    async def test_unavailable_missing_engines_block_but_unknown_providers_are_valid(self):
        for field, domain in voice.ENGINE_FIELDS.items():
            for missing in (False, True):
                with self.subTest(field=field, missing=missing):
                    data = fixture()
                    if missing:
                        del data['states'][domain + '.fcc']
                    else:
                        data['states'][domain + '.fcc']['state'] = 'unavailable'
                    with self.assertRaisesRegex(voice.SafeError, 'pipeline_engine_unavailable'):
                        voice.plan_switch(data, self.mapping, 'fcc')
        self.assertEqual(len(voice.plan_switch(fixture(), self.mapping, 'fcc')), 3)

    def test_unknown_or_unavailable_selector_blocks_writes_but_status_works(self):
        for state in ('unknown', 'unavailable'):
            self.ha.data['states']['select.dot']['state'] = state
            with self.assertRaisesRegex(voice.SafeError, 'assistant_select_unavailable'):
                voice.plan_switch(self.ha.data, self.mapping, 'fcc')
            result = voice.status(self.ha.data, self.mapping)
            self.assertFalse(result['selectors'][2]['available'])
            self.assertFalse(result['backends']['fcc']['ready'])
            self.assertNotIn('select.dot', json.dumps(result))

    def test_duplicate_pipeline_names_are_not_safe_even_when_id_is_explicit(self):
        self.ha.data['pipelines'].append(dict(self.ha.data['pipelines'][1], id='another-id'))
        with self.assertRaisesRegex(voice.SafeError, 'pipeline_name_not_unique'):
            voice.plan_switch(self.ha.data, self.mapping, 'fcc')

    async def test_partial_failure_rolls_back_only_confirmed_writes(self):
        self.ha.fail_write = 2
        with self.assertRaisesRegex(voice.SafeError, '^switch_failed_manual_recovery_required$'):
            await self.switch()
        self.assertEqual(self.ha.writes, [('select.show_one', 'Fcc'), ('select.show_two', 'Fcc'),
                                         ('select.show_one', 'Homeway')])
        self.assertEqual([item['status'] for item in self.journal()['changes']],
                         ['rolled_back', 'write_pending', 'planned'])
        self.assertEqual(self.ha.data['states']['select.dot']['state'], 'Homeway')

    async def test_lost_response_after_server_write_is_marked_uncertain_not_overwritten(self):
        def lost_reply(client):
            if len(client.writes) == 2:
                raise ConnectionError('SECRET server payload')
        self.ha.after_write = lost_reply
        with self.assertRaisesRegex(voice.SafeError, 'manual_recovery_required'):
            await self.switch()
        self.assertEqual(self.ha.data['states']['select.show_one']['state'], 'Homeway')
        self.assertEqual(self.ha.data['states']['select.show_two']['state'], 'Fcc')
        self.assertEqual(self.ha.writes[-1], ('select.show_one', 'Homeway'))
        self.assertEqual(self.journal()['changes'][1]['status'], 'write_pending')

    async def test_pipeline_replaced_under_same_name_after_preflight_is_not_selected(self):
        changes = voice.plan_switch(await self.ha.inventory(), self.mapping, 'fcc')
        self.ha.data['pipelines'][1]['id'] = 'replacement-id'
        with self.assertRaisesRegex(voice.SafeError, 'switch_failed_rolled_back'):
            await voice.execute(self.ha, changes, self.snapshot)
        self.assertEqual(self.ha.writes, [])

    async def test_observed_concurrent_change_before_write_rolls_back_previous_only(self):
        def drift(client):
            if len(client.writes) == 1:
                client.external_change('select.show_two', 'Other')
        self.ha.after_write = drift
        with self.assertRaisesRegex(voice.SafeError, '^switch_failed_rolled_back$'):
            await self.switch()
        self.assertEqual(self.ha.writes, [('select.show_one', 'Fcc'), ('select.show_one', 'Homeway')])
        self.assertEqual(self.ha.data['states']['select.show_two']['state'], 'Other')

    async def test_rollback_refuses_external_overwrite_of_our_completed_change(self):
        def drift(client):
            if len(client.writes) == 2:
                client.external_change('select.show_one', 'Other')
        self.ha.after_write = drift
        self.ha.fail_write = 3
        with self.assertRaisesRegex(voice.SafeError, 'manual_recovery_required'):
            await self.switch()
        self.assertEqual(self.ha.data['states']['select.show_one']['state'], 'Other')
        self.assertEqual(self.journal()['changes'][0]['status'], 'conflict')
        self.assertEqual(self.ha.writes[-1], ('select.show_two', 'Homeway'))

    async def test_restore_uses_cas_and_refuses_same_value_rewritten_later(self):
        await self.switch()
        self.ha.external_change('select.show_one', 'Other')
        self.ha.external_change('select.show_one', 'Fcc')
        with self.assertRaisesRegex(voice.SafeError, 'restore_concurrent_change'):
            await voice.plan_restore(self.ha, self.journal())
        self.assertEqual(len(self.ha.writes), 3)

    async def test_restore_preflight_then_roundtrip_and_idempotence(self):
        await self.switch()
        original = self.journal()
        changes = await voice.plan_restore(self.ha, original)
        self.assertEqual(len(self.ha.writes), 3)  # Planning does not write.
        await voice.execute(self.ha, changes, self.root / 'private' / 'restore.json', 'restore')
        self.assertTrue(all(self.ha.data['states'][entity]['state'] == 'Homeway'
                            for entity in self.mapping['assistant_selects']))
        for item in original['changes']:
            item['status'] = 'restored'
        self.assertEqual(await voice.plan_restore(self.ha, original), [])

    async def test_default_switch_and_restore_each_require_explicit_opt_in(self):
        await self.switch(include_default=True)
        self.assertEqual(self.ha.data['preferred'], 'fcc-id')
        with self.assertRaisesRegex(voice.SafeError, 'default_restore_requires_include_default'):
            await voice.plan_restore(self.ha, self.journal())
        plan = await voice.plan_restore(self.ha, self.journal(), include_default=True)
        self.assertEqual(plan[0]['kind'], 'preferred')
        self.assertEqual(plan[0]['after_value'], 'homeway-id')

    async def test_restore_of_preferred_selector_uses_restored_default_pipeline(self):
        self.ha.data['states']['select.show_one']['state'] = 'preferred'
        await self.switch(include_default=True)
        plan = await voice.plan_restore(self.ha, self.journal(), include_default=True)
        await voice.execute(self.ha, plan, self.root / 'private' / 'restore.json', 'restore')
        self.assertEqual(self.ha.data['preferred'], 'homeway-id')
        self.assertEqual(self.ha.data['states']['select.show_one']['state'], 'preferred')

    async def test_restore_blocks_wrong_instance_unavailable_target_and_uncertain_journal(self):
        await self.switch()
        original = self.journal()
        bad = copy.deepcopy(original)
        bad['origin_sha256'] = 'b' * 64
        with self.assertRaisesRegex(voice.SafeError, 'instance_mismatch'):
            await voice.plan_restore(self.ha, bad)
        bad = copy.deepcopy(original)
        bad['changes'][0]['status'] = 'write_pending'
        with self.assertRaisesRegex(voice.SafeError, 'uncertain_changes'):
            await voice.plan_restore(self.ha, bad)
        self.ha.data['states']['stt.homeway']['state'] = 'unavailable'
        with self.assertRaisesRegex(voice.SafeError, 'pipeline_engine_unavailable'):
            await voice.plan_restore(self.ha, original)
        self.assertEqual(len(self.ha.writes), 3)

    async def test_existing_snapshot_is_never_overwritten_before_mutation(self):
        self.snapshot.parent.mkdir()
        self.snapshot.write_text('existing')
        with self.assertRaises(FileExistsError):
            await self.switch()
        self.assertEqual(self.snapshot.read_text(), 'existing')
        self.assertEqual(self.ha.writes, [])

    def test_private_paths_reject_public_files_and_symlink_escape(self):
        with self.assertRaisesRegex(voice.SafeError, 'project_private'):
            voice.save_snapshot(self.root / 'README.md', {}, initial=True)
        self.assertFalse((self.root / 'README.md').exists())
        (self.root / 'outside').mkdir()
        (self.root / 'private').symlink_to(self.root / 'outside', target_is_directory=True)
        with self.assertRaisesRegex(voice.SafeError, 'symlink'):
            voice.save_snapshot(self.snapshot, {}, initial=True)
        self.assertEqual(list((self.root / 'outside').iterdir()), [])

    def test_credentials_require_one_source_and_never_echo_invalid_value(self):
        env = {'HA_URL': 'https://ha.example.invalid', 'HA_TOKEN': 'SECRET'}
        self.assertEqual(voice.credentials(env), (env['HA_URL'], 'SECRET'))
        env['HA_TOKEN_FILE'] = '/private/token'
        with self.assertRaisesRegex(voice.SafeError, '^set_exactly_one_token_source$'):
            voice.credentials(env)
        env = {'HA_URL': 'https://user:SECRET@example.invalid', 'HA_TOKEN': 'SECRET'}
        with self.assertRaisesRegex(voice.SafeError, '^invalid_ha_url$'):
            voice.credentials(env)

    def test_remote_http_is_rejected_before_reading_a_bearer_token(self):
        for origin in ('http://ha.example.invalid', 'http://192.168.1.2:8123',
                       'http://localhost.example.invalid', 'http://127.1',
                       'http://[2001:db8::1]:8123'):
            for opt_in in (None, '', '0', 'true', 'yes'):
                with self.subTest(origin=origin, opt_in=opt_in), \
                        mock.patch.object(Path, 'read_text') as read_token:
                    env = {'HA_URL': origin, 'HA_TOKEN_FILE': '/private/SECRET'}
                    if opt_in is not None:
                        env['HA_ALLOW_INSECURE_HTTP'] = opt_in
                    with self.assertRaisesRegex(voice.SafeError, '^ha_url_requires_https$'):
                        voice.credentials(env)
                    read_token.assert_not_called()

    def test_https_loopback_and_explicit_insecure_opt_in_are_supported(self):
        for origin in ('https://ha.example.invalid', 'http://localhost:8123',
                       'http://127.0.0.1:8123', 'http://[::1]:8123'):
            with self.subTest(origin=origin):
                self.assertEqual(voice.credentials({'HA_URL': origin, 'HA_TOKEN': 'SECRET'}),
                                 (origin, 'SECRET'))
        env = {'HA_URL': 'http://ha.example.invalid:8123', 'HA_TOKEN': 'SECRET',
               'HA_ALLOW_INSECURE_HTTP': '1'}
        self.assertEqual(voice.credentials(env), (env['HA_URL'], 'SECRET'))
        for origin in ('ftp://ha.example.invalid', 'http://user:SECRET@ha.example.invalid',
                       'http://ha.example.invalid?token=SECRET', 'http://ha.example.invalid#SECRET',
                       'http://ha.example.invalid:invalid'):
            with self.subTest(origin=origin):
                env['HA_URL'] = origin
                with self.assertRaisesRegex(voice.SafeError, '^invalid_ha_url$'):
                    voice.credentials(env)

    def test_main_does_not_print_raw_transport_errors(self):
        error = io.StringIO()
        with mock.patch.object(sys, 'argv', ['voice_pipeline.py', 'status']), \
                mock.patch.object(voice, 'run', new=mock.AsyncMock(
                    side_effect=RuntimeError('SECRET https://private.invalid'))), \
                mock.patch.object(sys, 'stderr', error):
            with self.assertRaises(SystemExit):
                voice.main()
        self.assertNotIn('SECRET', error.getvalue())
        self.assertNotIn('private.invalid', error.getvalue())

    async def test_cli_switch_and_restore_default_to_read_only(self):
        path = self.root / 'private' / 'mapping.json'
        path.parent.mkdir()
        path.write_text(json.dumps(self.mapping))
        fake = self.ha
        class ContextClient:
            def __init__(self, *args):
                pass
            async def __aenter__(self):
                return fake
            async def __aexit__(self, *args):
                pass
        args = mock.Mock(command='switch', mapping=path, backend='fcc',
                         include_default=False, apply=False)
        with mock.patch.object(voice, 'HAClient', ContextClient), \
                mock.patch.dict(os.environ, {'HA_URL': 'https://ha.example.invalid',
                                             'HA_TOKEN': 'SECRET'}, clear=True):
            result = await voice.run(args)
            self.assertTrue(result['dry_run'])
            self.assertEqual(fake.writes, [])
            await self.switch()
            args = mock.Mock(command='restore', snapshot=self.snapshot,
                             include_default=False, apply=False)
            result = await voice.run(args)
            self.assertTrue(result['dry_run'])
            self.assertEqual(len(fake.writes), 3)

    async def test_ws_write_payloads_match_ha_api(self):
        client = voice.HAClient('https://ha.example.invalid', 'SECRET')
        client.request = mock.AsyncMock()
        await client.write({'kind': 'select', 'entity_id': 'select.show_one'}, 'Fcc')
        client.request.assert_awaited_with('call_service', domain='select', service='select_option',
            service_data={'entity_id': 'select.show_one', 'option': 'Fcc'})
        await client.write({'kind': 'preferred'}, 'fcc-id')
        client.request.assert_awaited_with('assist_pipeline/pipeline/set_preferred', pipeline_id='fcc-id')


if __name__ == '__main__':
    unittest.main()

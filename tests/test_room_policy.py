"""Room policy validation, template decisions and restart/expiry transitions."""
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_remote_endpoint as endpoint
from test_remote_endpoint import actions, fixture, walk

try:
    from jinja2.nativetypes import NativeEnvironment
except ImportError:
    NativeEnvironment = None


def room_fixture():
    value = fixture()
    value.update(sip_call_entity='sensor.fixture_sip_call', sip_registration_entity='sensor.fixture_sip_registration', room={
        'actions': {'lights': {'type': 'light', 'entity_id': 'light.fixture', 'operation': 'toggle'},
                    'heating': {'type': 'climate', 'entity_id': 'climate.fixture', 'temperature': 21},
                    'music': {'type': 'endpoint', 'mode': 'music', 'audio_media_id': 'https://audio.example.invalid/radio'},
                    'scene': {'type': 'scene', 'entity_id': 'scene.fixture'},
                    'routine': {'type': 'script', 'entity_id': 'script.fixture'},
                    'timer': {'type': 'timer', 'seconds': 300, 'label': 'Tea'}},
        'status': {'temperature': 'sensor.temperature'}, 'presence': ['binary_sensor.door', 'binary_sensor.motion'],
        'announcement': {'tts_entity': 'tts.fixture', 'quiet_start': 22, 'quiet_end': 8, 'max_seconds': 30}})
    return value


class RoomValidationTests(unittest.TestCase):
    def test_options_are_immutable_and_scripts_are_fixed(self):
        value = room_fixture()
        before = copy.deepcopy(value)
        package = endpoint.render_package(value)
        self.assertEqual(value, before)
        self.assertEqual(package['script']['show5_fixture_room_lights']['sequence'],
                         [{'service': 'light.toggle', 'target': {'entity_id': 'light.fixture'}}])
        self.assertNotIn('fields', package['script']['show5_fixture_room_music'])
        self.assertIn('mode', package['script']['show5_fixture_command']['fields'])
        for script in package['script'].values():
            self.assertEqual(script['trace']['stored_traces'], 0)
        self.assertEqual(len(actions(package, 'androidtv.adb_command')), 1)

    def test_rejects_unbounded_or_wrong_domain_actions(self):
        invalid = [None, [], {'actions': {'x': {'type': 'shell', 'command': 'id'}}},
                   {'actions': {'action': {'type': 'scene', 'entity_id': 'scene.x'}}},
                   {'actions': {'timer_command': {'type': 'scene', 'entity_id': 'scene.x'}}},
                   {'actions': {'message_command': {'type': 'scene', 'entity_id': 'scene.x'}}},
                   {'actions': {'x': {'type': {}, 'entity_id': 'script.x'}}},
                   {'actions': {'x': {'type': 'endpoint', 'mode': {}}}},
                   {'actions': {'x': {'type': 'light', 'entity_id': 'switch.x', 'operation': 'toggle'}}},
                   {'actions': {'x': {'type': 'climate', 'entity_id': 'climate.x', 'temperature': 100}}},
                   {'actions': {'x': {'type': 'timer', 'seconds': True, 'label': 'Timer'}}},
                   {'actions': {'x': {'type': 'timer', 'seconds': 1, 'label': '{{secret}}'}}},
                   {'actions': {'x': {'type': 'endpoint', 'mode': 'music', 'audio_media_id': 'https://u:p@host/path'}}},
                   {'actions': {'x': {'type': 'endpoint', 'mode': 'music', 'audio_media_id': 'https://host:abc/path'}}},
                   {'actions': {'x': {'type': 'endpoint', 'mode': 'tv', 'preset': 'missing'}}},
                   {'presence': ['sensor.not_presence']}, {'presence': ['binary_sensor.x', 'binary_sensor.x']},
                   {'announcement': {'tts_entity': 'script.shell'}},
                   {'announcement': {'tts_entity': 'tts.x', 'quiet_start': 24}},
                   {'announcement': {'tts_entity': 'tts.x', 'max_seconds': 1000}}]
        for room in invalid:
            with self.subTest(room=room), self.assertRaises(ValueError):
                endpoint.render_package(dict(fixture(), room=room))
        for value in ('media_player.wrong', '{{sensor.x}}', None):
            with self.assertRaises(ValueError):
                endpoint.render_package(dict(fixture(), sip_call_entity=value))
        with self.assertRaises(ValueError):
            endpoint.render_package(dict(fixture(), sip_registration_entity='sensor.x'))

    def test_library_bluetooth_sendspin_are_fixed_and_optional(self):
        config = room_fixture()
        package = endpoint.render_package(config)
        commands = endpoint.fixed_operations(config)
        self.assertIn('android.settings.BLUETOOTH_SETTINGS', commands['start_bluetooth'])
        self.assertIn('org.videolan.vlc', commands['start_library'])
        self.assertNotIn('sendspin', package['script']['show5_fixture_command']['fields']['mode']['selector']['select']['options'])
        config['app_ids']['sendspin'] = 'org.example.sendspin'
        package = endpoint.render_package(config)
        self.assertIn('show5_fixture_room_sendspin', package['script'])
        self.assertIn('stop_sendspin', endpoint.fixed_operations(config))
        for op in ('start_bluetooth', 'start_library', 'start_sendspin'):
            self.assertIn('ro.serialno', endpoint.fixed_operations(config)[op])
        self.assertNotIn('am force-stop com.android.settings', json.dumps(package))

    def test_timer_and_message_transactions_share_one_queue_each(self):
        scripts = endpoint.render_package(room_fixture())["script"]
        for command, operations in (("timer_command", ("set_timer", "cancel_timer", "timer_finish")),
                                    ("message_command", ("message", "dismiss"))):
            worker = "show5_fixture_room_" + command
            self.assertEqual(scripts[worker]["mode"], "queued")
            self.assertEqual(scripts[worker]["max"], 10)
            for operation in operations:
                steps = scripts["show5_fixture_room_" + operation]["sequence"]
                self.assertEqual(len(steps), 1)
                self.assertEqual(steps[0]["service"], "script." + worker)
                self.assertEqual(steps[0]["data"]["operation"], operation)

    def test_no_announcements_without_tts_binding(self):
        package = endpoint.render_package(dict(fixture(), room={}))
        self.assertNotIn('show5_fixture_room_announce', package['script'])
        self.assertNotIn('announce', package['script']['show5_fixture_command']['fields']['mode']['selector']['select']['options'])
        self.assertFalse(actions(package, 'tts.speak'))


@unittest.skipIf(NativeEnvironment is None, 'Install the pinned Jinja2 test dependency to evaluate HA templates')
class RoomTemplateTests(unittest.TestCase):
    def setUp(self):
        self.config = room_fixture()
        self.package = endpoint.render_package(self.config)
        self.values = {'input_select.show5_fixture_active_mode': 'idle', 'media_player.fixture_vaca': 'idle',
                       'sensor.fixture_sip_call': 'idle', 'sensor.fixture_sip_registration': 'registered',
                       'media_player.fixture_android': 'on', 'switch.fixture_mute': 'off'}
        self.attributes = {'sensor.fixture_sip_call': {'call_id': None, 'lease_held': False}}
        self.ts = datetime(2026, 10, 29, 12, tzinfo=timezone.utc).timestamp()
        self.env = NativeEnvironment()
        self.env.tests['match'] = lambda value, pattern: re.match(pattern, value) is not None
        self.env.globals.update(states=lambda entity: self.values.get(entity, 'unknown'),
                                is_state=lambda entity, state: self.values.get(entity) == state,
                                state_attr=lambda entity, attr: self.attributes.get(entity, {}).get(attr),
                                now=lambda: datetime.fromtimestamp(self.ts, timezone.utc),
                                as_timestamp=lambda value: value.timestamp())
        self.calls = []

    def render(self, value, context=None):
        if isinstance(value, str):
            return self.env.from_string(value).render(**(context or {}))
        if isinstance(value, dict):
            return {key: self.render(item, context) for key, item in value.items()}
        return value

    def run_steps(self, sequence, context=None):
        context = dict(context or {})
        for row in sequence:
            if 'if' in row:
                matched = all(self.render(condition['value_template'], context) is True for condition in row['if'])
                self.run_steps(row['then'] if matched else row.get('else', []), context)
            elif 'choose' in row:
                for branch in row['choose']:
                    if self.render(branch['conditions'], context) is True:
                        self.run_steps(branch['sequence'], context)
                        break
            elif 'stop' in row:
                if row.get('error'):
                    raise ValueError(row['stop'])
                return
            elif 'service' in row:
                service = row['service']
                entity = row.get('target', {}).get('entity_id')
                data = self.render(row.get('data', {}), context)
                self.calls.append((service, entity, data))
                if service.startswith('script.'):
                    self.run_steps(self.package['script'][service[7:]]['sequence'], data)
                elif service.startswith('input_boolean.'):
                    self.values[entity] = 'on' if service.endswith('turn_on') else 'off'
                elif service == 'input_text.set_value':
                    self.values[entity] = data['value']
                elif service == 'input_datetime.set_datetime':
                    self.attributes[entity] = {'timestamp': data['timestamp']}
                elif service == 'timer.start':
                    self.values[entity] = 'active'
                elif service == 'timer.cancel':
                    self.values[entity] = 'idle'
                else:
                    raise AssertionError('Unexpected effect in timer test: ' + service)
            else:
                raise AssertionError('Unsupported test action: ' + repr(row))

    def run_script(self, name, **fields):
        self.run_steps(self.package['script']['show5_fixture_room_' + name]['sequence'], fields)

    def test_all_generated_templates_parse_for_optional_profiles(self):
        for quiet in ((22, 8), (8, 22), (0, 0)):
            config = room_fixture()
            config['room']['announcement'].update(quiet_start=quiet[0], quiet_end=quiet[1])
            config['app_ids']['sendspin'] = 'org.example.sendspin'
            for item in walk(endpoint.render_package(config)):
                if isinstance(item, str) and '{{' in item:
                    self.env.parse(item)

    def test_sip_guard_blocks_active_missing_or_partially_released_call(self):
        sequence = self.package['script']['show5_fixture_command']['sequence']
        self.assertEqual(sequence[0]['service'], 'homeassistant.update_entity')
        condition = sequence[1]['if'][0]['value_template']
        for state, held, call_id, blocked in [('idle', False, None, False), ('error', False, None, False),
                ('ringing', False, 'call', True), ('active', True, 'call', True), ('error', True, None, True),
                ('idle', False, 'old-call', True), ('unknown', None, None, True)]:
            self.values['sensor.fixture_sip_call'] = state
            self.attributes['sensor.fixture_sip_call'] = {'lease_held': held, 'call_id': call_id}
            with self.subTest(state=state, held=held, call_id=call_id):
                self.assertIs(self.render(condition), blocked)
        self.values['sensor.fixture_sip_call'] = 'idle'
        self.attributes['sensor.fixture_sip_call'] = {'lease_held': False, 'call_id': None}
        cleanup = next(row for row in self.package['automation'] if row['id'].endswith('_remote_after_call'))
        self.assertIs(self.render(cleanup['condition'][-1]['value_template']), True)
        for helper in ('display', 'refresh'):
            self.assertEqual(self.package['script']['show5_fixture_' + helper]['sequence'][:2], sequence[:2])

    def test_announcement_checks_busy_quiet_and_deadline_before_effects(self):
        sequence = self.package['script']['show5_fixture_command']['sequence']
        row = next(item for item in sequence if item.get('if') == [{'condition': 'template', 'value_template': "{{ mode == 'announce' }}"}])
        context = {'mode': 'announce', 'message': 'Doorbell', 'expires_at': self.ts + 30}
        self.run_steps([row], context)
        self.assertEqual(self.calls, [])
        for changes, error in [({'message': 'X' * 241}, '1 to 240'), ({'expires_at': self.ts - 1}, 'expired'),
                               ({'expires_at': self.ts + 1000}, 'expired'), ({'expires_at': True}, 'expired')]:
            with self.assertRaisesRegex(ValueError, error):
                self.run_steps([row], dict(context, **changes))
        self.values['input_select.show5_fixture_active_mode'] = 'jitsi'
        with self.assertRaisesRegex(ValueError, 'busy'):
            self.run_steps([row], context)
        self.values['input_select.show5_fixture_active_mode'] = 'idle'
        self.values['media_player.fixture_vaca'] = 'playing'
        with self.assertRaisesRegex(ValueError, 'busy'):
            self.run_steps([row], context)
        self.values['media_player.fixture_vaca'] = 'idle'
        self.ts += 11 * 3600
        with self.assertRaisesRegex(ValueError, 'quiet hours'):
            self.run_steps([row], dict(context, expires_at=self.ts + 30))
        duration = next(row['data']['duration'] for row in sequence if row.get('service') == 'timer.start')
        self.assertEqual(self.render(duration, {'mode': 'announce'}), 30)
        self.assertEqual(self.render(duration, {'mode': 'camera_front', 'camera_seconds': 45}), 45)
        self.assertEqual(self.render(duration, {'mode': 'music', 'lease_minutes': 20}), 1200)
        self.assertFalse(actions(self.package, 'media_player.volume_set'))

    def test_timer_restart_expiry_only_once_and_old_event_cannot_finish_new_timer(self):
        self.run_script('set_timer', seconds=10, label='Tea')
        self.assertEqual(self.values['timer.show5_fixture_room_timer'], 'active')
        self.run_script('timer_finish')
        self.assertNotEqual(self.values.get('input_boolean.show5_fixture_room_message_visible'), 'on')
        self.ts += 11
        # Simulate HA restart after the restore timer has already expired.
        self.values['timer.show5_fixture_room_timer'] = 'idle'
        self.run_script('timer_finish')
        self.assertEqual(self.values['input_text.show5_fixture_room_message_text'], 'Timer complete: Tea')
        self.assertEqual(self.values['input_boolean.show5_fixture_room_timer_armed'], 'off')
        effects = lambda: [call for call in self.calls if not call[0].startswith('script.')]
        count = len(effects())
        self.run_script('timer_finish')
        self.assertEqual(len(effects()), count)
        self.run_script('dismiss')
        self.run_script('set_timer', seconds=300, label='New timer')
        self.run_script('timer_finish')
        self.assertEqual(self.values['input_boolean.show5_fixture_room_message_visible'], 'off')
        self.run_script('cancel_timer')
        self.ts += 400
        self.run_script('timer_finish')
        self.assertEqual(self.values['input_boolean.show5_fixture_room_message_visible'], 'off')

    def test_presence_does_not_convert_missing_inputs_to_vacancy(self):
        from types import SimpleNamespace
        self.env.globals["expand"] = lambda entities: [SimpleNamespace(state=self.values[entity]) for entity in entities if entity in self.values]
        sensor = next(row for group in self.package["template"] for row in group.get("binary_sensor", []))
        self.values["binary_sensor.door"] = "off"
        self.assertIs(self.render(sensor["availability"]), False)
        self.values["binary_sensor.motion"] = "unavailable"
        self.assertIs(self.render(sensor["availability"]), False)
        self.values["binary_sensor.door"] = "on"
        self.assertIs(self.render(sensor["availability"]), True)
        self.assertIs(self.render(sensor["state"]), True)
        self.values["binary_sensor.door"] = "off"
        self.values["binary_sensor.motion"] = "off"
        self.assertIs(self.render(sensor["availability"]), True)
        self.assertIs(self.render(sensor["state"]), False)
        self.assertEqual(sensor["delay_off"], {"seconds": 180})

    def test_missing_status_entity_reports_unknown_without_timestamp_error(self):
        class MissingStates:
            def __call__(self, entity):
                return "unknown"
            def __getitem__(self, entity):
                return None
        self.env.globals["states"] = MissingStates()
        sensor = next(row for group in self.package["template"] for row in group.get("sensor", []) if row["unique_id"].endswith("_room_status"))
        value = self.render(sensor["attributes"]["temperature"])
        self.assertEqual(value, {"state": "unknown", "unit": None, "updated_at": None})

    def test_message_expiry_hides_content_and_rejects_old_input(self):
        self.run_script('message', message='<b>Doorbell</b>', expires_at=self.ts + 60)
        sensor = next(row for group in self.package['template'] for row in group.get('sensor', []) if row['unique_id'].endswith('_room_reminder'))
        self.assertEqual(self.render(sensor['state']), 'active')
        self.assertEqual(self.render(sensor['attributes']['message']), '<b>Doorbell</b>')
        self.ts += 61
        self.assertEqual(self.render(sensor['state']), 'none')
        self.assertEqual(self.render(sensor['attributes']['message']), '')
        with self.assertRaisesRegex(ValueError, 'expiry'):
            self.run_script('message', message='Late', expires_at=self.ts - 10)
        with self.assertRaisesRegex(ValueError, '1 to 240'):
            self.run_script('message', message='', expires_at=self.ts + 10)


if __name__ == '__main__':
    unittest.main()

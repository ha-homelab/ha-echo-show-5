"""Provisioning boundaries; no Android, network or microphone access."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('sip_provision', Path(__file__).parents[1] / 'provision.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def settings():
    return {'schema': 1, 'endpoint_id': 'show_one', 'sip': {
        'username': 'example', 'password': 'test-only-placeholder', 'domain': 'pbx.example.invalid:5060',
        'transport': 'tcp', 'display_name': 'Show One'},
        'contacts': [{'id': 'desk', 'label': 'Desk', 'address': 'sip:desk@pbx.example.invalid:5060'}],
        'max_call_seconds': 120}


class ProvisionTests(unittest.TestCase):
    def test_valid_private_profile(self):
        self.assertEqual(m.validate(settings())['endpoint_id'], 'show_one')

    def test_rejects_unknown_fields_and_unbounded_calls(self):
        for key, value in [('shell', 'arbitrary'), ('max_call_seconds', 0), ('max_call_seconds', 1801), ('max_call_seconds', True)]:
            data = settings(); data[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                m.validate(data)

    def test_address_cannot_inject_headers_or_shell_commands(self):
        for address in ['sip:a@host\r\nX: injected', 'sip:a@host;transport=tcp', 'sip:a@host?Subject=x',
                        'sip:a@host$(id)', 'sip:a@host name', 'tel:123', 'https://example.invalid']:
            data = settings(); data['contacts'][0]['address'] = address
            with self.subTest(address=address), self.assertRaises(ValueError):
                m.validate(data)

    def test_duplicate_or_missing_contact_is_rejected(self):
        for contacts in [[], [settings()['contacts'][0]] * 2, [{'id': 'desk', 'address': 'sip:desk@host'}]]:
            data = settings(); data['contacts'] = contacts
            with self.assertRaises(ValueError): m.validate(data)

    def test_valid_ipv6_and_invalid_account_domains(self):
        for domain in ['pbx.example.invalid', '192.0.2.5:5060', '[2001:db8::1]:5061']:
            m.host(domain)
        for domain in ['user:password@host', 'host/path', 'host?query', 'host#fragment', 'host:0', 'host:65536']:
            with self.subTest(domain=domain), self.assertRaises(ValueError): m.host(domain)

    def test_only_regular_private_bounded_file(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'settings.json'; p.write_text(json.dumps(settings())); p.chmod(0o600)
            self.assertTrue(m.read_private(p))
            p.chmod(0o644)
            with self.assertRaises(ValueError): m.read_private(p)
            p.chmod(0o600)
            link = Path(directory) / 'link.json'; link.symlink_to(p)
            with self.assertRaises(ValueError): m.read_private(link)
            p.write_bytes(b' ' * (m.MAX_BYTES + 1))
            with self.assertRaises(ValueError): m.read_private(p)

    def test_status_rejects_multiple_rows_and_errors(self):
        self.assertEqual(m.parse_status('Row: 0 json={"schema":1,"state":"idle"}')['state'], 'idle')
        for raw in ['No result found.', 'Row: 0 json={"schema":2}', 'Row: 0 json={"schema":1}\nRow: 1 json={"schema":1}']:
            with self.subTest(raw=raw), self.assertRaises(ValueError): m.parse_status(raw)

    def test_device_identity_failure_precedes_import(self):
        d = m.Device('adb', '192.0.2.4:5555', 'SERIAL1234')
        with patch.object(d, 'shell', return_value='OTHER') as call:
            with self.assertRaises(ValueError): d.verify()
            self.assertEqual(call.call_args.args, ('getprop', 'ro.serialno'))

    def test_content_write_is_guarded_and_secret_only_stdin(self):
        d = m.Device('adb', '192.0.2.4:5555', 'SERIAL1234')
        secret = b'private-password'
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'', b'')) as run:
            d.shell('content', 'write', '--uri', 'content://org.hahomelab.show5sip/config', data=secret)
            command = run.call_args.args[0][-1]
            self.assertIn('getprop ro.serialno', command)
            self.assertIn('id -u', command)
            self.assertIn('SERIAL1234', command)
            self.assertNotIn(secret.decode(), str(run.call_args.args))
            self.assertEqual(run.call_args.kwargs['input'], secret)

    def test_android_security_rejection_is_not_success(self):
        d = m.Device('adb', '192.0.2.4:5555', 'SERIAL1234')
        with patch.object(m.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'java.lang.SecurityException', b'')):
            with self.assertRaises(ValueError): d.status()


if __name__ == '__main__':
    unittest.main()

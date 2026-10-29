#!/usr/bin/env python3
"""Validate/import private SIP settings through an authenticated, exact-device ADB connection."""
import argparse
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import time
from urllib.parse import urlsplit

AUTHORITY = 'org.hahomelab.show5sip'
MAX_BYTES = 65536


def text(value, name, limit=128):
    if not isinstance(value, str) or not value or len(value) > limit or any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError('Invalid ' + name)
    return value


def host(value):
    text(value, 'SIP domain', 253)
    parsed = urlsplit('sip://' + value)
    if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password or not parsed.hostname:
        raise ValueError('SIP domain must be host[:port]')
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        if not re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?', parsed.hostname):
            raise ValueError('Invalid SIP host') from None
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError('Invalid SIP port')


def validate(config):
    required = {'schema', 'endpoint_id', 'sip', 'contacts', 'max_call_seconds'}
    if not isinstance(config, dict) or set(config) != required or type(config['schema']) is not int or config['schema'] != 1:
        raise ValueError('Expected SIP settings schema 1 with only documented fields')
    if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', text(config['endpoint_id'], 'endpoint_id', 48)):
        raise ValueError('Invalid endpoint_id')
    sip = config['sip']
    if not isinstance(sip, dict) or set(sip) != {'username', 'password', 'domain', 'transport', 'display_name'}:
        raise ValueError('Invalid SIP account fields')
    if not re.fullmatch(r'[A-Za-z0-9_.+-]{1,80}', text(sip['username'], 'SIP username', 80)):
        raise ValueError('Invalid SIP username')
    text(sip['password'], 'SIP password', 512)
    if not text(sip['display_name'], 'display name', 80).strip():
        raise ValueError('Invalid display name')
    host(sip['domain'])
    if sip['transport'] not in {'udp', 'tcp', 'tls'}:
        raise ValueError('Unknown SIP transport')
    if type(config['max_call_seconds']) is not int or not 10 <= config['max_call_seconds'] <= 1800:
        raise ValueError('Call limit must be 10..1800 seconds')
    contacts = config['contacts']
    if not isinstance(contacts, list) or not 1 <= len(contacts) <= 64:
        raise ValueError('Expected 1..64 allowlisted contacts')
    seen = set()
    for contact in contacts:
        if not isinstance(contact, dict) or set(contact) != {'id', 'label', 'address'}:
            raise ValueError('Invalid contact fields')
        identifier = text(contact['id'], 'contact ID', 48)
        if not re.fullmatch(r'[a-z][a-z0-9_]{0,47}', identifier) or identifier in seen:
            raise ValueError('Invalid or duplicate contact ID')
        seen.add(identifier)
        if not text(contact['label'], 'contact label', 80).strip():
            raise ValueError('Invalid contact label')
        address = text(contact['address'], 'contact address', 512)
        match = re.fullmatch(r'sip:([A-Za-z0-9_.+-]{1,80})@([^\s;?<>]+)', address)
        if not match or match[2] != sip['domain']:
            raise ValueError('Contact must be an exact address on the configured SIP server')
        host(match[2])
    return config


def read_private(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Settings must be a regular private file')
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise ValueError('Settings permissions must exclude group/other access (chmod 600)')
    data = path.read_bytes()
    if len(data) > MAX_BYTES:
        raise ValueError('Settings exceed 64 KiB')
    validate(json.loads(data))
    return data


def parse_status(output):
    # Android content query renders a single `json` column as `Row: 0 json={...}`.
    start = output.find('{')
    if start < 0:
        raise ValueError('SIP status did not return JSON')
    result, end = json.JSONDecoder().raw_decode(output[start:])
    if output[start + end:].strip() or not isinstance(result, dict) or result.get('schema') != 1:
        raise ValueError('Unexpected SIP status response')
    return result


class Device:
    def __init__(self, adb, target, serial):
        if not re.fullmatch(r'[A-Za-z0-9_.:\[\]-]{4,128}', target):
            raise ValueError('Invalid exact ADB target')
        if not re.fullmatch(r'[A-Za-z0-9_-]{4,80}', serial):
            raise ValueError('Expected full hardware serial')
        self.command = [str(adb), '-s', target]
        self.serial = serial

    def shell(self, *args, data=None):
        command = shlex.join(args)
        if args and args[0] == 'content':
            command = ('[ "$(getprop ro.serialno)" = ' + shlex.quote(self.serial) + ' ] && '
                       '[ "$(getprop ro.product.device)" = cronos ] && '
                       '[ "$(getprop ro.build.version.release)" = 11 ] && '
                       '[ "$(id -u)" = 2000 ] && [ "$(getprop ro.adb.secure)" = 1 ] && ' + command)
        result = subprocess.run(self.command + ['shell', '-T', command], input=data,
                                capture_output=True, timeout=25)
        if result.returncode:
            raise ValueError('ADB action failed; credentials were not printed')
        output = result.stdout.decode('utf-8', errors='replace').strip()
        if any(marker in output for marker in ('SecurityException', 'Error while accessing provider', 'Exception occurred')):
            raise ValueError('Android rejected the protected operation')
        return output

    def verify(self):
        if (self.shell('getprop', 'ro.serialno') != self.serial or
                self.shell('getprop', 'ro.product.device') != 'cronos' or
                self.shell('getprop', 'ro.build.version.release') != '11' or
                self.shell('id', '-u') != '2000' or
                self.shell('getprop', 'ro.adb.secure') != '1'):
            raise ValueError('Wrong device or insecure/root ADB; no settings imported')

    def status(self):
        return parse_status(self.shell('content', 'query', '--uri', 'content://' + AUTHORITY + '/status'))


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['validate', 'apply', 'status'])
    parser.add_argument('--config', type=Path)
    parser.add_argument('--adb', default='adb')
    parser.add_argument('--target')
    parser.add_argument('--expected-serial')
    args = parser.parse_args()
    if args.action != 'status' and args.config is None:
        parser.error('--config is required')
    data = read_private(args.config) if args.config else None
    if args.action == 'validate':
        settings = json.loads(data)
        print(json.dumps({'valid': True, 'endpoint_id': settings['endpoint_id'], 'contacts': len(settings['contacts'])}))
        return
    if not args.target or not args.expected_serial:
        parser.error('--target and --expected-serial are required')
    device = Device(args.adb, args.target, args.expected_serial)
    device.verify()
    if args.action == 'status':
        print(json.dumps(device.status(), indent=2))
        return
    before = device.status()
    if before.get('lease_held') or before.get('call_id') or before.get('state') not in ('idle', 'unconfigured', 'stopped'):
        raise ValueError('An active call or lease blocks reprovisioning')
    device.shell('content', 'write', '--uri', 'content://' + AUTHORITY + '/config', data=data)
    expected = hashlib.sha256(data).hexdigest()
    for _ in range(30):
        current = device.status()
        if current.get('config_sha256') == expected and current.get('configured') is True:
            print(json.dumps({'imported': True, 'endpoint_id': json.loads(data)['endpoint_id'], 'config_sha256': expected}))
            return
        if current.get('config_error'):
            raise ValueError('Application rejected settings; inspect its sanitized status')
        time.sleep(.2)
    raise ValueError('Import acknowledgement missing; do not assume settings were accepted')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, json.JSONDecodeError, subprocess.SubprocessError) as error:
        # Parser errors may include the sensitive input; expose only our validated
        # messages and exception class for transport/JSON failures.
        if type(error) is ValueError:
            raise SystemExit(str(error)) from None
        raise SystemExit('Operation failed (' + type(error).__name__ + '); no credentials printed') from None

#!/usr/bin/env python3
"""Render a native HA dashboard into private storage; no network or HA writes."""
import argparse
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / 'templates' / 'home-assistant'
TOKEN = re.compile(r'\$\{([A-Z_]+)\}')
ENTITY = re.compile(r'[a-z_]+\.[a-z0-9_]+')
PATH_KEYS = {'DASHBOARD_PATH', 'MAIN_HOME_PATH'}


def render(template, mapping, example, states=None):
    if not isinstance(template, dict) or not isinstance(mapping, dict) or not isinstance(example, dict):
        raise ValueError('Template and mappings must be JSON objects')
    raw = json.dumps(template)
    required = set(TOKEN.findall(raw))
    if set(mapping) != required or set(example) != required:
        raise ValueError('Mapping must contain exactly the documented template keys')
    for key, value in mapping.items():
        if not isinstance(value, str) or 'replace_me' in value or '${' in value:
            raise ValueError('Replace every example value with an explicit local mapping')
        if key == 'DASHBOARD_PATH':
            if not re.fullmatch(r'/[a-z][a-z0-9_-]*', value):
                raise ValueError('Dashboard path must be one local path segment')
        elif key == 'MAIN_HOME_PATH':
            if not re.fullmatch(r'/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/?', value):
                raise ValueError('Main home path must be a local path without query parameters')
        elif not ENTITY.fullmatch(value) or value.split('.')[0] != example[key].split('.')[0]:
            raise ValueError('Entity mapping has an invalid ID or the wrong domain: ' + key)
    if states is not None:
        if not isinstance(states, list) or any(not isinstance(row, dict) or
                not isinstance(row.get('entity_id'), str) for row in states):
            raise ValueError('States must be a local JSON array of HA state objects')
        known = {row['entity_id'] for row in states}
        if any(value not in known for key, value in mapping.items() if key not in PATH_KEYS):
            raise ValueError('At least one mapped entity is absent from the supplied state inventory')

    def replace(value):
        if isinstance(value, str):
            return TOKEN.sub(lambda match: mapping[match.group(1)], value)
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    return replace(template)


def write_private(output, value, root=ROOT):
    private = (root / 'private').resolve()
    # A private/ symlink outside the project would defeat the ignored-output boundary.
    if private != root.resolve() / 'private':
        raise ValueError('Project private directory must not resolve outside the project')
    destination = output.resolve()
    if private not in destination.parents:
        raise ValueError('Rendered output must stay inside this project private directory')
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(str(destination), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--states', type=Path,
                        help='Optional existing private JSON export of HA entity states')
    args = parser.parse_args()
    try:
        example = json.loads((TEMPLATES / 'mapping.example.json').read_text())
        template = json.loads((TEMPLATES / 'dashboard.template.json').read_text())
        mapping = json.loads(args.mapping.read_text())
        states = json.loads(args.states.read_text()) if args.states else None
        output = render(template, mapping, example, states)
        write_private(args.output, output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print('Rendered private dashboard; HA was not contacted or changed. '
          + ('Entity names matched the supplied inventory.' if states is not None
             else 'Entity availability has not been checked.'))


if __name__ == '__main__':
    main()

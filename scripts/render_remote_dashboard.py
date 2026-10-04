#!/usr/bin/env python3
"""Render the phone/desktop controls for a device-bound remote endpoint."""
import argparse
import json
from pathlib import Path

from render_remote_endpoint import validate_config, write_private


def render_dashboard(config):
    c = validate_config(config)
    p = c['prefix']

    def button(name, icon, mode, **fields):
        return {'type': 'button', 'name': name, 'icon': 'mdi:' + icon,
                'tap_action': {'action': 'perform-action',
                               'perform_action': 'script.' + p + '_command',
                               'data': dict(mode=mode, **fields)}}

    cards = [
        {'type': 'markdown', 'content': '# Show remote\nChoose what runs on this display. Calls open a muted prejoin screen; join on the Show. Home ends the session and restores the clock.'},
        {'type': 'grid', 'columns': 3, 'square': False, 'cards': [
            button('Home / Stop', 'home', 'home'),
            button('Front', 'cctv', 'camera_front'),
            button('Porch', 'cctv', 'camera_porch'),
            button('Video call', 'video', 'jitsi'),
            button('OTTPlay web', 'web', 'ottplay'),
            button('OttPlayer', 'television-play', 'ottplayer'),
        ]},
    ]
    if 'ottplay_native' in c['app_ids']:
        cards[1]['cards'].append(button('OTTPlay app', 'play-box', 'ottplay_native'))
    cards += [
        {'type': 'markdown', 'content': '## Music\nOpen **Choose music**, select a source, then Run. The session ends after 30 minutes. Volume and playback controls apply to the Show.'},
        {'type': 'button', 'name': 'Choose music', 'icon': 'mdi:music',
         'entity': 'script.' + p + '_play_audio',
         'tap_action': {'action': 'more-info'}},
        {'type': 'media-control', 'entity': c['vaca_media_entity']},
    ]
    if c['tv_presets']:
        cards += [
            {'type': 'markdown', 'content': '## Television\nPreset streams open in VLC for 30 minutes.'},
            {'type': 'grid', 'columns': 3, 'square': False,
             'cards': [button(value['label'], 'television', 'tv', preset=key)
                       for key, value in c['tv_presets'].items()]},
        ]
    cards.append({'type': 'grid', 'columns': 2, 'square': False, 'cards': [
        {'type': 'button', 'entity': 'input_select.' + p + '_active_mode',
         'name': 'Active mode', 'show_state': True,
         'tap_action': {'action': 'none'}, 'hold_action': {'action': 'none'}},
        {'type': 'button', 'entity': 'timer.' + p + '_lease',
         'name': 'Time remaining', 'show_state': True,
         'tap_action': {'action': 'none'}, 'hold_action': {'action': 'none'}},
    ]})
    cards.append({'type': 'entities', 'title': 'Voice and connection', 'entities': [
        {'entity': c['vaca_mute_entity'], 'name': 'Voice assistant muted'},
        {'entity': 'script.' + p + '_refresh', 'name': 'Refresh clock connection'},
    ]})
    return {'title': 'Show remote', 'views': [{'title': 'Remote', 'path': 'remote',
                                             'icon': 'mdi:remote', 'cards': cards}]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        write_private(args.output, render_dashboard(json.loads(args.config.read_text())))
    except (ValueError, OSError):
        parser.error('Invalid local bindings or unavailable private output')
    print('Rendered private dashboard; no HA changes were made.')


if __name__ == '__main__':
    main()

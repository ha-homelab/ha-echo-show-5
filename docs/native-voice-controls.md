# Native media and screen voice commands

The FCC conversation bridge is a text-answer fallback. Supported household
commands should run in Home Assistant before that fallback, with
`prefer_local_intents: true` on both the Homeway and FCC pipelines. Changing the
model prompt cannot supply missing player routing or a music catalogue.

`scripts/render_voice_controls.py` creates one sentence automation and a queued
dispatcher per configured endpoint. The installed HA conversation trigger
supplies `trigger.satellite_id` and `trigger.device_id`; HA resolves the device
from the satellite registry when possible. The package prefers the configured
satellite mapping, then the device mapping. Explicit configured names also work
from typed Assist. An unknown origin without an explicit target receives a
request to specify the device and performs no action. No default household
speaker is guessed.

## Music prerequisites

Use the existing Music Assistant server and authenticated Plex provider. For a
VACA Show, add its verified VACA media entity to the existing **Home Assistant
Media Players** provider in Music Assistant. Preserve the existing selected
players. Use the resulting **Music Assistant** media entity in this package,
not the original VACA entity: the MA entity owns search, queue and playlist
playback. The source is a private list of 1–25 approved Plex track URIs, sampled from the
existing local Music Assistant library. A bounded list avoids expanding an
entire large smart playlist for a new request. It does not cancel an already
running playlist load, guarantee startup latency or establish audible playback.
Confirm each mapping on its own device before enabling voice commands.

Play resumes an existing Plex queue, preserves an already playing track, and
loads the bounded default track list only for an empty or different queue. Pause retains
the queue. After a server restart, a current item may have a `library://track/`
URI and no stream details. An available mapping to the exact configured Plex
provider preserves that queue; a mapping to another provider or an unavailable
mapping does not. A known different stream provider takes precedence over a
library item's fallback mappings. The package does not assume a Plex `media-source://`
URL exists. Arbitrary artists or songs are outside this small command set.

The operator can refresh the private seed from the existing MA client with
`ma.music.get_library_tracks(limit=25, provider=provider_id, order_by="random")`.
Keep only available tracks with a mapping to that exact Plex provider, save
their URIs as `default_tracks`, rerender, check and reload scripts. No user
transcript supplies these IDs. A seed remains fixed until the next refresh.

## Render and deploy

Copy `examples/home-assistant/voice-controls.example.json` into ignored
`private/voice-controls/` storage with mode 0600. Replace all illustrative
identities, aliases, player entities, provider and default track URIs. Include each
existing Dot separately so generic music commands preserve its own player.
Configure `remote_script` only for a Show with the separately verified
[remote endpoint](remote-endpoint.md). Keep real bindings out of Git.

```bash
python3 scripts/render_voice_controls.py \
  --config private/voice-controls/config.json \
  --output private/voice-controls/package-v1.yaml
```

The renderer refuses shared or ambiguous device, satellite, player and alias
bindings, template syntax, arbitrary service names and external media URLs.
Output is JSON-compatible YAML, private-only, mode 0600, and must be a new file.
Review it, back up the existing live files, check the full HA configuration and
reload scripts and automations through the normal deployment procedure. This
does not require changing satellite firmware or the FCC/Homeway selection.

Remove conflicting unqualified legacy music sentences before activation. The
earlier `custom_sentences/{ru,en}/plex_music.yaml` maps all generic commands to
`script.echo_plex_music`, which targets one fixed Dot. Preserve that script for
existing callers. Either remove just its sentence files from the active loader,
or narrow them to a distinct required suffix such as `на старом эхо` / `on the
legacy echo` that is absent from the new package's aliases. Reload conversation
sentences and test both languages. Do not run two handlers for the same phrase.

## Commands and lifetime

- `Включи музыку`, `Останови музыку`, `Продолжи музыку`, `Следующий трек`.
- `Установи громкость 35 процентов` (integer 0–100).
- `Покажи часы`, `Открой OTTPlay`, `Покажи переднюю камеру`, `Покажи камеру крыльца`.
- Append a configured name, for example `на втором шоу`. Equivalent English
  commands and explicit names are included; spoken confirmations are Russian.

Commands without a name operate only on their registered origin. A Dot responds
that it has no screen for screen commands. A Show returns from its previous
owned app session before music starts/resumes. Switching to the clock, OTT or a
camera stops only that Show's MA music first. Screen operations retain the remote
endpoint's existing camera and application leases. MA music runs until its queue
finishes, is paused, stopped or replaced; it does not create the direct-URL remote endpoint's lease.
The handoff sends Stop to the available MA entity even when it reports `idle`:
VACA buffering can temporarily appear idle while an MA stream session remains
active. When that entity is missing, unknown or unavailable, screen commands
remain usable without a music service call. A failed Stop on an available entity
aborts the handoff instead of reporting success.
The dashboard Home action alone does not own this MA queue; the voice clock
command explicitly stops it before invoking Home.

Services run synchronously before a success reply. A player service failure
propagates as an error; the package never replaces a failed action with a success
claim. Service acceptance still does not prove audible playback or camera video.
Traces are disabled for the generated scripts and automation. HA service logs,
state and recordings may still contain private media metadata.

## Recovering a stalled Music Assistant request

Check the target queue's `extra_attributes.play_action_in_progress` together
with its item count and state. In the inspected MA version, playlist expansion
and Stop share the player's playback lock: Stop may wait behind a pending
load. Clearing a queue or closing the requesting WebSocket does not cancel that
server task. A missing player after an HA reconnect does not establish that an
old request was cancelled. Do not accumulate repeated Play requests.

A Music Assistant restart affects its other active players. Before an approved
restart, refresh a private snapshot with `players/all`, `player_queues/all`, and
`player_queues/items` for each active queue; paginate when needed. Record the
current queue item ID, progress timestamp, volume and group membership. Normal
MA shutdown stops playback and flushes queue state to its persistent cache.
This is recovery behavior, not a guarantee after a forced shutdown.

After startup, verify each previously playing queue's identity, items and player
availability before using `player_queues/resume`. If exact position restoration
is required, the supported `player_queues/play_index` API accepts the saved
queue item ID as `index` and integer seconds as `seek_position`. Use a fresh
snapshot and account for its progress timestamp; do not treat an old raw
`elapsed_time` value as the current position. Restore only queues that were
playing, preserve previously paused/idle devices and existing group coordinators,
and verify playback and volume independently. Do not replace a lost household
queue with this package's default track seed as an automatic recovery shortcut.

## Verification

Run `python3 -m unittest discover -s tests -p test_voice_controls.py`. The native
execution cases require the deployed HA Python runtime; they create an isolated
HA with fake media services and never call household devices. They verify origin
isolation, no-action unknown origins, bounded volume, queue reuse, screen handoff,
service failure, sentence recognition and unrelated commands remaining unmatched.

Then verify typed Assist with explicit targets, genuine satellite-origin requests,
audible playback and stop/restore on each device. Keep a before snapshot, avoid
interrupting other active players and restore the tested device's prior volume.

# Room controls and session policy

The room extension adds fixed Home Assistant actions, expiring messages,
restorable timers and room status to the existing device-bound endpoint package.
It reuses the endpoint's command queue, session token, media cleanup and microphone
restoration. It does not create another always-running Android recorder.

## Configure and render

Add optional bindings to the private JSON used by
[`render_remote_endpoint.py`](../scripts/render_remote_endpoint.py). Device
identities, server addresses, entity names and media sources belong in private
configuration; the example below uses placeholders.

```json
{
  "sip_call_entity": "sensor.example_sip_call",
  "sip_registration_entity": "sensor.example_sip_registration",
  "room": {
    "actions": {
      "lights": {"type": "light", "entity_id": "light.example", "operation": "toggle"},
      "heating": {"type": "climate", "entity_id": "climate.example", "temperature": 21},
      "music": {"type": "endpoint", "mode": "music", "audio_media_id": "https://radio.example.invalid/live"},
      "camera": {"type": "endpoint", "mode": "camera_front", "camera_seconds": 60},
      "phone": {"type": "endpoint", "mode": "jitsi", "lease_minutes": 30},
      "tea": {"type": "timer", "seconds": 300, "label": "Tea"}
    },
    "status": {"temperature": "sensor.example_temperature", "heater_power": "sensor.example_power"},
    "presence": ["binary_sensor.example_motion", "binary_sensor.example_door"],
    "presence_clear_seconds": 180,
    "announcement": {"tts_entity": "tts.example", "language": "en", "quiet_start": 22, "quiet_end": 8, "max_seconds": 30}
  }
}
```

Merge this object with the required device bindings; it is not a complete
endpoint configuration. Render to a new ignored file, validate the merged HA
configuration, back up the previous package, then install the package using the
normal HA change window. Re-rendering alone makes no live changes.

```sh
python3 scripts/render_remote_endpoint.py \
  --config private/room/config.json \
  --output private/room/package.json
```

The `room` object is optional. Omitting it retains the original endpoint API.
Both SIP bindings are optional, but a registration binding requires the call
binding. Deploy the SIP call binding on devices running the native SIP pilot.

## Fixed actions

For prefix `example`, action key `lights` produces
`script.example_room_lights`, taking no arguments. The generic
`script.example_room_action` accepts only one configured action key. Neither
interface accepts an Android shell command, intent, arbitrary service name or
runtime media URL. Configuration can bind a fixed scene or an existing script;
those trusted routines retain their own permissions and resource behavior.

The supported action types are `endpoint`, `light`, `climate`, `scene`, `script`
and `timer`. Climate targets are fixed temperatures between 5 and 35 °C; use a
suitably configured existing routine for a different unit or range.
Default wrappers include Home, Stop, Front, Porch, Jitsi, OTTPlay web, VLC library,
Bluetooth settings and a five-minute timer. Native OTTPlay and Sendspin wrappers
are generated only when their package identifiers are bound.

New endpoint modes have concrete, limited behavior:

- `library` opens the installed VLC library. Its local-network browser can use
  supported NAS protocols after the operator configures access inside VLC.
  The package neither publishes NAS credentials nor assumes a configured share.
- `bluetooth` opens Android Bluetooth settings. It does not enable discovery,
  pair an unknown phone or claim successful A2DP playback. Home closes the visible
  settings page; it does not disconnect an independently paired audio source.
- `sendspin` launches the configured player package and includes it in owned
  session cleanup. Binding an app ID does not configure a Music Assistant server
  or establish measured synchronization; those require separate acceptance.

Existing camera modes retain the bounded full-screen display path. Existing TV
presets retain fixed URLs. Music routes through the configured VACA player.

## Calls and shared resources

When a SIP call sensor is configured, every endpoint command, direct display
command and VACA refresh first requests a fresh sensor update. It proceeds only
when the sensor reports `idle` or terminal `error`, `lease_held` is false, and
`call_id` is null. Unknown or partially released state blocks the operation.
Thus Home, motion-related scripted display launches and new media commands cannot
intentionally replace an observed active native call.

An expired endpoint session blocked by a call is reconciled when the call sensor
changes again. Session tokens still prevent an old cleanup request from ending a
newly acquired endpoint session. Jitsi retains explicit saved-mute restoration;
phone control buttons remain the interface for answering or ending native calls.

This is **layered HA coordination, not an atomic Android-wide media lock**. A
native incoming call can begin after an HA check. Native inbound and outbound
SIP commands do not consult the remote endpoint mode; they can overlap an
existing Jitsi or player session. Independently launched apps can also bypass
the endpoint, and the SIP/VACA lease does not cover arbitrary Android
applications. Do not infer simultaneous Jitsi/SIP or camera/microphone acceptance
from a healthy status entity. Hardware privacy controls remain authoritative.

## Announcements and expiring messages

`script.example_room_message` accepts `message` (1–240 characters) and
`expires_at` (a future Unix timestamp, at most one hour ahead). Its output is
`sensor.example_room_reminder`: state `active` or `none`, with `message` and
`expires_at` attributes. Expired content disappears from the sensor without
replaying it after restart. `script.example_room_dismiss` acknowledges it.
The display must render message text as text, never HTML.

When a TTS entity is bound, `script.example_room_announce` accepts the same text
limit and a deadline no more than 120 seconds ahead. It goes through the endpoint
queue and rechecks the deadline when it executes. It rejects requests during a
call, another owned session, existing player activity, unavailable state, or quiet
hours. This deliberately avoids interrupting music or ducking a volume that the
user set. No mute or volume setting is changed. TTS caching is disabled for these
short messages. See the [HA TTS reference](https://www.home-assistant.io/integrations/tts/).

Quiet hours use **HA's local timezone**. A range such as 22 → 8 crosses midnight;
8 → 22 stays within a day. Equal start/end disables quiet hours. A configured
5–60 second endpoint lease bounds cleanup after playback starts; a stalled HA/TTS
service call can delay execution of queued cleanup, so this is not an audio
watchdog or an emergency announcement channel.

## Timers and outages

`script.example_room_set_timer` takes `seconds` (1–86400) and a short `label`.
Set, cancel and expiry execute through one shared queue, so an old expiry
cannot interleave with and cancel a new timer. The queue stores an absolute
deadline and armed flag alongside the restorable
`timer.example_room_timer`. `script.example_room_cancel_timer` disarms it first,
then cancels the timer.

HA checks the absolute deadline on timer completion, at startup and once a minute.
An expiry that happened while HA was stopped therefore produces a visible
“Timer complete” reminder after HA returns. An old event cannot complete a newly
started future timer. Once emitted, the armed flag is cleared; periodic checks do
not repeat the same reminder. A failure partway through delivery can retry the
same visual reminder instead of silently losing it.

This is a server timer with outage reconciliation. It cannot ring while HA is
offline. A browser countdown, a page-local chime and an Android OS alarm have
different lifetimes; the room display documents its local timer separately.
Nothing here claims persistence through a powered-off Show. HA documents the
missing startup event in its [timer reference](https://www.home-assistant.io/integrations/timer/).

## Status and presence

Generated entities include:

- `sensor.example_room_session`: current endpoint owner or `phone`, with `busy`
  and lease end attributes. Missing SIP state is conservatively busy.
- `sensor.example_room_health`: HA entity availability and, when configured,
  SIP registration. `ready` does not prove acoustic/video quality or a recent
  physical interaction.
- `sensor.example_room_status`: configured source values, units and update times.
  Source timestamps must be displayed as stale when appropriate; a cached number
  is not a fresh measurement.
- `binary_sensor.example_room_presence`, only with configured binary inputs:
  OR-combined occupancy with a 30–3600 second vacancy hold. A positive sensor wins;
  if none is positive and any source is missing, availability is unknown rather
  than inventing vacancy.

The package does not infer occupancy from a paired phone, light level, fake
battery value or a missing hardware sensor. Reuse existing VACA lux entities
instead of opening a second sensor collector. No additional Android permissions
are required for the room package itself.

## Validation

Offline checks cover fixed bindings, optional player behavior, native-call guard
states, generated Jinja syntax, announcement quiet hours/deadlines, timer expiry
while HA was down, cancelled/replaced timers and expiring message contents.
Install the pinned development dependency to run the template checks locally:

```sh
python3 -m pip install 'Jinja2==3.1.6'
python3 -m unittest discover -s tests -p 'test_room_policy.py'
python3 -m unittest discover -s tests -p 'test_remote_endpoint.py'
```

These tests do not replace HA configuration validation or per-device playback,
call, screen and reconnect acceptance. Keep device-specific deployment receipts
private and identify any unperformed physical checks in the delivery report.

## Sendspin pilot acceptance — 2026-10-29

Both installed SendspinDroid 2.0.0 clients were registered as distinct Music
Assistant 2.10.8 players, **Show One** and **Show Two**. Their initial queues were
empty, idle and ungrouped. The second Show then ran one bounded test using an
existing Plex-library track. The interval from play command to confirmed stop
was **10.92 seconds**.

The Android client negotiated **Opus, 48 kHz, 16-bit stereo**. Retained client
counters showed **870 chunks received, 370 played and zero dropped**. It reported
zero underruns, inserted/dropped correction frames, re-anchors, filled gaps and
trimmed overlaps. Music Assistant returned the endpoint to idle, cleared only
the test item, and restored its original volume. Other players' playback and
group membership were unchanged. These are transport/decoder observations; no
human listening test or long-duration synchronization test was performed.

Both the client's protocol screen and established socket showed a direct LAN
connection between the NUC and the second Show. The NUC initiated the connection
to the Show's Sendspin listener. This establishes the final media hop; it does
not establish the upstream route from the Plex library to Music Assistant.
Private receipts contain the exact player identifiers, socket endpoints and
before/after snapshots. No new playback group was created.

## AirPlay receiver on the NUC — Show Two pilot

The installed MA server advertises the `airplay_receiver` plugin, marked
**alpha** and limited to one configured instance. On **2026-10-29**, it was enabled
for the verified **Show Two** player only, with the advertised name **Show Two**.
The existing `airplay` player provider sends audio to AirPlay speakers; the new
receiver plugin provides the opposite direction from an iPhone.

The receiver's installed source provides these runtime options:

- `connected_players`: optional list of MA player IDs; default empty. Only
  selected players are advertised, and an empty list leaves the plugin idle.
- `publish_name_template`: required choice controlling the advertised name;
  supported values are `player_mass` (default), `player`, and `mass_player`.
  They display player name followed by Music Assistant, player name only, or
  Music Assistant followed by player name, respectively.

One receiver process is created per selected player, using deterministically
assigned ports in the 7000–7999 range. The pilot verified one healthy receiver
process on the NUC, ownership of its IPv4 and IPv6 listener, and an exact
one-player configuration. All 28 pre-existing provider records and all observed
player playback, volume and group states remained unchanged. No playback was
started during activation. Phone discovery, audio, stop and volume recovery
still require an actual iPhone acceptance test before expanding the selection.

The intended route is **iPhone → AirPlay receiver on NUC → Sendspin → Show**.
The Show must keep its Sendspin player connected; receiver provisioning does not
prove that Android can wake a force-stopped player. Use the endpoint Sendspin
action to open it when necessary.
The official guide requires devices on the same network and describes approximately
five seconds of buffering, which makes this a music input rather than an
intercom path. Cross-subnet discovery has not been tested here.
[Music Assistant AirPlay Receiver guide](https://www.music-assistant.io/plugins/airplay-receiver/).

Provisioning used the supported `config/providers/setup` API to create an idle
instance, then read its runtime entries and used `config/providers/save` to select
only Show Two. The installed client's older domain-only schema request does not
match this server's runtime-instance API; the exact workflow and option values
were confirmed in installed source. No MA storage files were edited directly.

A private backup retains the original MA settings and provider inventory. The
activation receipt records the new instance ID and an exact
`config/providers/remove` rollback request. To roll back, verify that the recorded
instance is the `airplay_receiver` plugin and still targets only this Show, then
remove that instance. Do not remove the separate `airplay` player provider or
restore the complete settings file over unrelated later changes.

## Standalone OttPlayer distribution check

The separate OttPlayer app remains distinct from the installed OTTPlay FOSS
client. On **2026-10-29**, the [publisher's Android page](https://ottplayer.tv/soft/android)
advertised **OttPlayer 6.0.9** for Android newer than 5.0 and linked the
[official APK](https://ottplayer.tv/public/soft/OttPlayer_6.0.9.apk). Ordinary HTTPS
requests from the deployment environment returned **HTTP 403** for the page and
APK, including an APK request with the publisher page as its referrer.

No binary was obtained, installed or launched. Consequently the expected
`es.ottplayer.tv` package identifier, ARMv7 compatibility, manifest minimum SDK
and signing certificate remain unverified for that download. The fixed
OttPlayer endpoint mode retains its installed-package preflight and must not be
reported as a working installed app. Retry the publisher distribution when it is
accessible; this check did not use mirrors or bypass access challenges.

# Original plan: expanding an Android Show into a room endpoint

**Historical planning checkpoint.** This document preserves the expansion list
and evidence available before the October 29 implementation. Its “Build”,
“Configure”, app-parity and untested-function statements describe that checkpoint.
Use the [current capability delivery register](room-capability-delivery.md) for
what is now deployed, physically checked or still pending; use the
[room panel](room-panel.md) and [session policy](room-session-policy.md) for the
implemented behavior. The original list remains intact for traceability.

This is a capability plan for the already converted **Echo Show 5 Gen2 / cronos
running Android 11**, reviewed on **2026-10-29**. It does not install apps, grant
permissions, start recordings or enable new network services. The strongest
next step is to combine the working display, voice, media and call paths under
one room policy, then build useful automations from the sensors and services
already available.

See [Android and Home Assistant](android-and-home-assistant.md) for the ROM,
display and ADB baseline, [remote endpoint controls](remote-endpoint.md) for
existing commands, and [remote access options](android-remote-access.md) for
administration. A feature present in upstream Android or an app's catalog is a
candidate until the installed app, permissions and hardware have been checked.

## What the existing work already provides

The repository contains a small clock, motion-triggered full-screen camera
playback, guarded HA app launches, music/TV/player controls, a dual wake-word
path, and attended Jitsi integration. The **2026-10-29 SIP pilot** adds native
audio calls with a VACA microphone lease; its implementation is separately
tracked in [PR 115](https://github.com/ha-homelab/ha-echo-show-5/pull/115).
These are different owners of the same small device, not independent appliances.

Recorded SIP acceptance includes registration on both Shows, individual echo
calls, incoming/decline/answer/remote hangup through HA, bidirectional G722 RTP,
and return to VACA as the sole unsilenced recorder. It does **not** establish
human-rated acoustic quality, long-duration call reliability or simultaneous
Jitsi/SIP operation. Historical camera and player checks retain their original
scope in the linked runbooks; this plan does not silently renew those checks.

## What the current inventory changes

The read-only **2026-10-29** device and HA inventory establishes the following
boundaries for this plan. Private source receipts are retained separately;
household identities and raw state exports are not published here.

- Both devices expose exactly **one actual sensor: LIGHT**. VACA has an active
  listener and HA already receives numeric light-level entities in `lx` with
  the illuminance device class. No additional collector is needed for lux.
- Advertised accelerometer/compass feature flags do not correspond to sensors
  in the current HAL inventory. The motion selector is `none`; disabled motion
  states and old timestamps do not establish working room-presence detection.
- Bluetooth is on and the system dump includes **`A2dpSinkService`**. Receiving
  phone audio as a Bluetooth speaker is a promising new experiment, but no
  pairing or audible playback test was performed.
- The thermal service reports its HAL not ready and no cached temperatures.
  A nominal thermal status must not be interpreted as a measured room temperature.
- Both use Android 11 / API 30 with a 32-bit ARMv7 application ABI and roughly
  974 MiB total RAM. About 248–263 MiB was available at the sample, not reserved
  for new features. Both screens are 960 × 480 with manual brightness selected.
- VACA build 7010, HA Companion minimal, Jitsi, the IP camera app and native SIP
  are present on both. Native OTTPlay, its preview app and VLC were found only
  on Show two; a common HA action must not assume those players exist on Show one.

## Capability map

**Existing** means an implementation or dated result already exists here.
**Configure** means supported components can be combined after checking the
installed versions. **Build** means owned development is needed.
**Experiment** means support on this ROM remains unproven. Priorities describe
the expected value for this installation, not measured performance.

| Capability | Path and useful result | Status / priority | Acceptance that matters |
|---|---|---|---|
| Room clock and status | Large time, next timer and one relevant room state rather than a full desktop dashboard | Existing; extend UI / high | Readable from the room; no unexpected dimming |
| Front-door camera | Existing motion stream plus doorbell event and explicit manual view | Existing + configure / high | First decoded frame, bounded expiry, no old event replay |
| Room actions | Six large actions: lights, heating, music, camera, phone, Home | Configure / high | Correct room target and acknowledged action |
| Voice control | Preserve the installed wake models; expose useful room entities and deterministic media actions to Assist | Existing + configure / high | Actual spoken command, correct target and audible response |
| Phone endpoint | Existing SIP pilot and Jitsi video path, with clear End/Home | Existing pilot / high | Two-party sound/video and clean return to voice |
| Announcements | Short local TTS/chimes with priority, expiry, quiet hours and acknowledgement | Configure + arbitration / high | Audible delivery without corrupting a call or user volume |
| Timers and reminders | HA countdown state displayed in the clock; optional local alarm fallback | Configure + UI build / high | Expiry after HA reconnect, not just countdown animation |
| Lux-based context | Reuse the existing VACA illuminance entity for room-lighting decisions and optional display policy | HA entity verified; configure use / high | Fresh samples, useful room thresholds and no display feedback loop |
| Device health | App/version, free storage, uptime, connectivity, current screen and media owner | Configure + small collector / high | Distinguish stale data from a healthy zero value |
| Heating/energy glance | Show room temperature, setpoint, heater power and tariff/solar context from existing HA sensors | Configure / high | Values have units, timestamps and correct room binding |
| Presence fusion | Combine existing room motion/door sensors with recent touch or an opt-in BLE beacon | Configure / medium | No immediate vacancy from one missing beacon |
| BLE beacon scanner | Companion beacon monitoring for explicitly selected nearby beacons | Experiment / medium | Target discovery, range and reconnect tested on this ROM |
| BLE sensor proxy | Separate Android proxy application exposing advertisements/GATT to HA | Experiment / medium | One real sensor survives screen-off, reboot and media load |
| Bluetooth speaker receiver | Test the observed A2DP sink profile with audio from a paired phone | Experiment / high | Real sound, reconnect, volume and audio-focus recovery |
| Music/radio/OTT | Existing VACA/Music Assistant and installed player launch paths | Existing + configure / medium | Real decode, audible output, stop/return and volume restoration |
| Photo/info frame | Small cached album, calendar or weather cards; no heavy feed UI | Build or configure / medium | Bounded cache and useful offline content |
| Local room camera | Existing camera pilot as an explicitly started auxiliary stream | Existing pilot / medium | Other apps release camera; stream visibly stops on End |
| Sound-event detection | Reuse the existing audio capture pipeline for opt-in event metadata | Build / low until ownership is unified | Measured false alarms; no second hidden microphone recorder |
| Physical shortcuts | Foreground volume-key gesture or an existing paired remote opens one room action | Build / medium | Preserve ordinary volume control and the hardware privacy button |
| QR/visual workflows | Deliberate camera scan for a household label or setup code | Experiment / low | Readable image and explicit completion; no persistent capture |
| USB/Bluetooth accessories | Keyboard, speaker or adapter only after actual host/profile compatibility checks | Experiment / low | Enumerated device, stable power and supported Android driver |
| On-device AI server | Heavy ASR/LLM/video analytics would compete with the endpoint | Offload / low | Keep inference and transcoding on existing server infrastructure |

## Lux is useful, but it is not screen brightness

Android's light sensor measures illuminance; the screen-brightness control is
an output setting. Both audited Shows already publish light through VACA.
Companion also offers a light sensor when Android supplies one, but duplicating
the existing collector is unnecessary. Its normal sensor-update cadence is not
a promise of a low-latency motion trigger. Preserve source and freshness checks,
then perform a controlled light/dark change before choosing automation
thresholds. [Companion sensor reference](https://companion.home-assistant.io/docs/core/sensors/#light-sensor).

Useful applications are turning room lights on only when it is dark, choosing a
high-contrast clock palette, or detecting that a supposedly lit room remains
dark. Avoid estimating occupancy solely from lux: a lamp, curtain, reflection
or screen content can change the reading without a person entering.

Keep the current manual brightness baseline as the default. An optional later
policy should have a minimum readable brightness, separate enter/exit
thresholds, a sustained interval before changing, and a manual override.
Reading a menu, watching a camera, or making a call should inhibit automatic
dimming. Lux collection does not require re-enabling the Android automatic
brightness controller that previously made these devices difficult to read.

Android exposes sensors at runtime. A manifest feature declaration, a sysfs
name, or a sensor row copied from another tablet does not prove that cronos has
working proximity, motion, humidity, pressure or room-temperature sensors.
The current HAL inventory exposes none of those sensors. Recheck after a ROM
change rather than assuming that a new permission unlocks them. A proximity
sensor on a different supported device may only report near/far; it is not
automatically a room occupancy detector.
[Android sensor discovery](https://developer.android.com/develop/sensors-and-location/sensors/sensors_overview).

The ROM's documented battery value is artificial. Internal device or CPU
temperature is also not room temperature: use an existing HA environmental
sensor for heating decisions. A fixed room assignment is more useful than
requesting GPS/location tracking from a stationary display.

An additional software sensor could calculate voice activity or relative noise
level from VACA's existing PCM stream and publish only summary values. That
requires a reviewed VACA extension and consent for the particular use; another
recorder app would compete for the microphone. Uncalibrated PCM amplitude is not
an accurate room sound-pressure measurement in dB SPL. A camera-based motion
sensor similarly consumes the camera and must participate in the same ownership
policy as calls; the existing outdoor motion event is usually the cheaper input.

## One room policy is more valuable than more background apps

The first owned development should be a small **endpoint session coordinator**.
It would expose a stable `mode`, `owner`, expiry and restoration status in HA,
while leaving each media implementation responsible for its own cleanup.
This is a proposal, not a claim that the current SIP lease already covers all
applications.

Suggested behavior:

1. An active call keeps the microphone and foreground screen. A motion camera
   event becomes a small pending indication instead of replacing the call.
2. A manual camera, TV or music request keeps its intended bounded session.
   Repeated motion cannot restart or indefinitely extend an unrelated session.
3. A short announcement is queued, ducked or rejected according to that session's
   policy. It never silently unmutes a deliberately muted microphone.
4. End/Home closes the owned media, releases microphone/camera resources,
   restores the previous volume/display/mute state, and returns to the clock.
5. Restart/reconnect reconciles the recorded owner with actual app/media state.
   It does not replay expired commands or start an old call.

The SIP pilot coordinates its own native recorder with VACA. Legacy Jitsi and
the camera/intercom path still require their existing explicit handoff. Android
can silence one recorder when applications compete, so a running service alone
does not prove usable sound. A unified policy should reuse one capture path or
transfer ownership, not run multiple always-listening apps.
[Android audio-input sharing](https://developer.android.com/media/platform/sharing-audio-input).

## Make room controls useful on five inches

The default view should answer one question quickly: time, active timer,
temperature/setpoint, or who is calling. Put optional controls on a single
large-target page and keep the clock one action away. Camera video retains the
existing full-screen presentation without redundant titles or timestamps.

Good HA compositions include a heating card with current temperature and power,
a bedtime action that sets the room state, a morning card with the next event,
and a doorbell action that opens the relevant camera. These consume entities
already managed by HA. They do not require granting the Show additional system
privileges or moving the HA server onto it.

For actionable messages, use a short title and at most two relevant actions:
for example **Show camera / Dismiss**, **Snooze / Done**, or **Call room / Close**.
Companion supports notification actions and app/deep links; use the existing
guarded endpoint commands for targets already mapped in this repository.
Never turn a notification field into an arbitrary shell or media-URL gateway.
[Companion notifications](https://companion.home-assistant.io/docs/notifications/notifications-basic/),
[notification command reference](https://companion.home-assistant.io/docs/notifications/notification-commands/).

HA timers can restore their state after a restart when configured to do so, but
an expiry while HA is down does not produce a delayed `timer.finished` event at
startup. A reminder implementation therefore needs an explicit overdue check.
A genuinely offline alarm needs a local alarm implementation and separate
reboot/time-zone tests; drawing a cached countdown is not that implementation.
[HA timer semantics](https://www.home-assistant.io/integrations/timer/).

## Presence and Bluetooth: separate roles

**A fixed Show broadcasting a beacon** identifies where that Show is. It does
not tell HA that a person is near it. **A Show observing a person's opt-in beacon**
can contribute to room presence, but RSSI is noisy and devices may stop
advertising. Combine it with existing motion/door events and generous expiry.
Companion's BLE transmitter and beacon-monitor features are the starting point,
subject to the installed flavor and this ROM's Bluetooth behavior.
[Companion Bluetooth sensors](https://companion.home-assistant.io/docs/core/sensors/#bluetooth-sensors).

**A BLE proxy** is different again: it forwards sensor advertisements or GATT
operations to HA. Enabling Android Bluetooth or Companion beacon monitoring
does not turn the device into HA's normal Bluetooth remote adapter.
[Supported HA remote adapters](https://www.home-assistant.io/integrations/bluetooth/#remote-adapters-bluetooth-proxies).

### A separate Bluetooth-audio opportunity

Both system inventories list `A2dpSinkService`, matching Android's
[A2DP sink implementation](https://android.googlesource.com/platform/packages/apps/Bluetooth/+/43e794fc5e64ae725d84aae86776098f010ae51a/src/com/android/bluetooth/a2dpsink/A2dpSinkService.java).
That is stronger evidence than a generic Bluetooth feature flag, but still not
proof of a working speaker receiver. A bounded pilot should pair one intended
phone, play audio, check volume and reconnect, then verify how incoming SIP,
Jitsi, VACA speech and local music obtain and release audio focus. Do not leave
the Show permanently discoverable or assume Bluetooth input participates in
the existing media-session lease. This could make the original speaker useful
to a phone without moving a music service onto the Show.

### An Android BLE proxy candidate

An exploratory no-new-hardware route exists:
[Home Assistant Mobile BLE Proxy](https://github.com/Zen3515/homeassistant-mobile-ble-proxy)
is an independent Android project implementing an ESPHome-compatible API,
advertisement forwarding and GATT connections, with optional Noise encryption.
Its author documents foreground-service operation and target-specific scanning
for screen-off use. This is **not installed or validated here**. Its
[current build configuration](https://github.com/Zen3515/homeassistant-mobile-ble-proxy/blob/main/app/build.gradle.kts)
declares `minSdk = 24`, which includes Android 11 at the API level; this does not
prove that a released APK and all dependencies work on cronos ARMv7. Before a pilot, check the
actual artifact, signature and maintenance status, then use one explicitly
selected existing BLE sensor. Validate
screen-off, Wi-Fi reconnect, device reboot, duplicate advertisements and
coexistence with voice/video. A successful first discovery is insufficient.

Do not assume Bluetooth Classic speaker or microphone profiles, IR transmitters,
Zigbee, Thread, Matter-controller roles or USB host support merely because a
generic Android settings screen is present. These require matching hardware,
drivers, profiles and application support. Existing HA radios can remain the
bridge while the Show supplies the interface.

## Additional protocol roles worth separating

These are candidates, not newly installed services. Reuse the existing server
where it can bridge protocols; a protocol's name alone does not imply that
the Show implements its receiver role.

| Role | Practical route | Required verification |
| --- | --- | --- |
| Multiroom audio | Trial Music Assistant's Sendspin web player; compare a compatible Android Sendspin or Snapcast client if background playback requires it | Installed MA version/provider, Android 11/ARMv7 client, screen-off continuity, audible synchronization and release for calls |
| AirPlay into the home audio system | Consider Music Assistant's server-side AirPlay Receiver plugin, then deliver audio to an accepted Show player | Server plugin availability, selected target, latency and media ownership; this does not make Android a native AirPlay receiver |
| NAS music/video | Use the installed VLC on Show two as an SMB/UPnP/DLNA client | Selected share credentials, codec/profile, throughput and clean return to the clock; browsing a DLNA server does not create a DLNA renderer |
| Device telemetry and named commands | A small owned MQTT client can publish health/availability and consume bounded, typed commands through HA | Broker identity/TLS, topic authorization, expiry and acknowledgements; do not retain transient call/start commands for replay after reconnect |
| Remote desktop | Prefer the documented host-side scrcpy path for Android maintenance; a VNC/RDP app would be a separately selected client or server | Direction of control, authentication, input support and screen size; neither protocol is implied by installing SSH |
| Camera protocols | Use the existing documented camera path; an RTSP/ONVIF endpoint needs an implementation that explicitly supplies it | Current camera ownership, codec/transport and teardown; Android camera permission alone supplies neither protocol |

Music Assistant documents its web player and Android Sendspin/Snapcast routes;
the current Sendspin guide labels the protocol a technical preview. Treat that
as a reason for a bounded pilot, not an installed-support claim.
Its AirPlay Receiver plugin is also described as early-stage, with about five
seconds of normal buffering delay; it is a music path, not an intercom path.
[MA Android/browser routes](https://www.music-assistant.io/faq/stream-to/),
[Sendspin](https://www.music-assistant.io/player-support/sendspin/),
[AirPlay Receiver plugin](https://www.music-assistant.io/plugins/airplay-receiver/).

VLC documents network-share playback, and HA documents MQTT discovery and
availability. A Show-side MQTT agent would still be new development, rather
than a permission toggle. Prefer VACA's existing entity connection for data it
already supplies, such as lux.
[VLC network playback](https://docs.videolan.me/vlc-user/android/3.X/en/browse/local_network.html),
[VLC project network capabilities](https://github.com/videolan/vlc-android),
[HA MQTT](https://www.home-assistant.io/integrations/mqtt/).

## Health, offline behavior and resource budget

A useful health report distinguishes **reachable**, **app ready**, **HA
authenticated**, **subscriptions ready**, **voice ready**, and **media ready**.
One green network ping cannot summarize those states. Preserve last-success
timestamps, current app/build, free storage, reconnect count, last failure code,
media owner and pending cleanup. Use sanitized bounded logs; routine monitoring
does not need transcripts, camera frames or every BLE device identifier.

Prefer event-driven reporting or a modest interval over continuous ADB polling.
Use the supported app APIs for routine state and reserve the guarded diagnostic
channel for investigation. Never call `dumpsys media.audio_flinger` on the
tested ROM: the project has recorded a vendor HAL crash from that command.
The existing [diagnostic limitation](android-and-home-assistant.md#audio-diagnostic-limitation-on-the-tested-rom)
and separate recorder/mute checks remain applicable.

The current clock can keep rendering while an already loaded page loses HA;
that is not proof of an offline cold start. A worthwhile extension is a small
packaged fallback clock and a visibly stale copy of the last room values, plus
bounded local chimes. After reconnect, reconcile current HA state and discard
old motion/media commands. Do not show an old temperature or camera image as
live data.

Keep the Show responsible for input, display, local wake detection and modest
media decoding. Existing server infrastructure should handle model inference,
camera analytics, transcoding and media indexing. There is no need to make the
five-inch endpoint a Kubernetes node, NAS or full database server to gain these
room features. A new background function earns its place by surviving a voice
request and camera/call transition without adding stalls or recorder conflicts.

## Recommended delivery order

1. **Use and maintain the factual inventory.** Lux is already connected. Recheck
   the observed app/build, permissions, storage and remote paths before each
   new feature; verify only the additional hardware assumptions that it needs.
   Keep private identifiers in private receipts.
2. **Expose existing value.** Add one concise room page, actionable reminders,
   heating/energy glance and diagnostic freshness. Keep English UI and the
   existing multilingual voice configuration separate.
3. **Unify ownership and recovery.** Extend the SIP/VACA handoff concept to
   Jitsi, camera, announcements and players; validate End/Home and reconnect.
4. **Add deliberate resilience.** A local fallback clock and overdue-reminder
   reconciliation provide more practical value than an additional shell daemon.
5. **Pilot one new hardware-facing feature.** Try an already owned BLE beacon
   or sensor before adding other background services. Publish the exact ROM,
   app version, observations and remaining limits.

Nothing in this plan requires another firmware conversion. Each implementation
should be independently deployable and removable, preserve the working voice
and display baseline, and record both its success conditions and its resource
ownership contract.

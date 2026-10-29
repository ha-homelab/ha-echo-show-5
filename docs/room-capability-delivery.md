# Room endpoint capability delivery

Checkpoint: **2026-10-29**. This document reconciles the complete expansion list
with implementation and observed deployment state. A source feature, an
installed application and a working physical feature are different results.

At this checkpoint, the room packages and `20261029-r13` display assets are
staged and the combined HA configuration passes its configuration check. **The
new room panel is not yet claimed live**: coordinated HA activation and device
acceptance remain. The existing voice, clock, camera and call paths retain their
earlier, separately scoped results.

![Room interface, HA policy, Android applications and administration routes](assets/room-runtime.svg)

## What has changed

- The room package adds fixed actions, native-call guards, bounded ownership,
  quiet-hour announcement checks, expiring messages, timer outage reconciliation,
  status and optional presence fusion. It reuses the existing endpoint queue.
- The display adds six large buttons, four readings, HA reminders, local timers,
  freshness indicators and an optional offline static page/photo cache. Automatic
  motion checks fresh room ownership and does not replace an open Room menu.
  Camera startup preserves the current interface until the first decoded frame;
  failure is silent and a working stream survives competing automatic motion.
- VLC and native OTTPlay now have installation parity on both Shows.
  **SendspinDroid 2.0 is installed on both**, with server configuration and
  playback acceptance still pending.
- The administration tool adds a checked scrcpy route, scoped file transfers,
  APK compatibility checks and sanitized health snapshots. A direct-LAN health
  snapshot succeeded on Show one. The NAS refused SSH forwarding; no policy was
  weakened. The user has authorized the Mac's ADB access to Show two, which still
  needs its own successful operation receipt.

The source suites and a synthetic Chrome session verify display logic, layout,
fixed actions, timer persistence and offline reload. They do not establish
audible playback, radio reception or an Android cold start.

## Status vocabulary

- **Implemented / staged:** source and relevant automated checks exist; live
  deployment or physical acceptance is still outstanding.
- **Installed / pending:** Android confirms the application is present; setup,
  decoding, sound, synchronization or recovery has not yet been demonstrated.
- **Existing / scoped:** the repository already contains the feature or earlier
  acceptance; this delivery does not silently renew that result.
- **Physical test pending:** a phone, beacon, sensor, accessory or attended
  observation is required. A permission grant is not a substitute.
- **Not implemented / not enabled:** an extension remains outside the delivered
  runtime. The row explains the next useful step.
- **Unsupported in this inventory:** the current hardware/ROM inventory does
  not expose the required capability.

## Complete capability register

| Capability from the expansion list | Delivered state at this checkpoint | Remaining acceptance or boundary |
| --- | --- | --- |
| Room clock and status | **Implemented / staged.** Large default clock; optional room panel, four readings, transport freshness and a current timer. | Activate r13 on both devices, then confirm readability and unchanged manual brightness. |
| Front-door camera and doorbell | **Existing + implemented / staged.** Existing Front/Porch stream path; fixed manual actions; fresh idle-owner and menu guards for automatic motion; expiring visual messages can accompany an event. | Verify a real motion/doorbell event after activation. A dedicated doorbell binding is still required where no existing event maps to it. |
| Room actions | **Implemented / staged.** Six configured buttons, with fixed endpoint, light, climate, scene, script or timer actions. Requests carry no arbitrary shell or service input. | Confirm each selected household binding affects the intended room. |
| Voice control | **Existing / scoped.** Existing VACA wake-word and Assist configuration is retained. Typed room scripts provide deterministic targets for HA. | New voice exposure and actual spoken requests require their own mapping and attended test; new scripts alone do not make an LLM call them correctly. |
| Phone endpoint | **Existing + implemented / staged.** Native SIP and Jitsi paths remain; HA media/display commands gain a fresh native-call guard. | Prior SIP checks covered bidirectional G.722 and return to VACA. This is not an Android-wide mutex; simultaneous independent SIP/Jitsi operation remains unaccepted. |
| Announcements | **Implemented / staged.** Bounded TTS request, expiry at execution, quiet hours, idle-player checks and no automatic volume/mute changes. | Bind an existing TTS entity and verify one short audible message, busy rejection and cleanup. No emergency-delivery guarantee. |
| Timers and reminders | **Implemented / staged.** Serialized HA set/cancel/expiry, absolute deadlines, startup overdue reconciliation and dismissible messages; local browser timer journal. | Verify HA restart reconciliation and device notification. Browser chimes require a live page, usable audio and idle ownership; a native OS alarm is not implemented. |
| Lux-based context | **Existing sensor + implemented display binding.** Reuse the numeric VACA illuminance entities already present on both Shows. | No duplicate collector or automatic dimming is enabled. Choose room automation thresholds only after a controlled light/dark test. |
| Device health | **Implemented; one direct-LAN device receipt.** Sanitized Android health command; HA entity/session health and display freshness are implemented. | Complete Show-two health and screen-control acceptance. Reachability and entity availability do not prove voice or media quality. |
| Heating/energy glance | **Implemented / staged.** Selected HA states, climate current temperature/setpoint and weather attributes fit four compact readings. | Confirm room/unit bindings; energy/tariff/solar views use existing HA data, not a new Show sensor. |
| Presence fusion | **Implemented / optional configuration.** OR-combined existing binary sensors, vacancy hold and conservative unknown availability. | Bind the correct room sensors. Lux, stale motion timestamps and a paired phone are not occupancy proof. |
| BLE beacon scanner | **Physical test pending; not configured.** No selected iBeacon or other opt-in beacon has been supplied. | Select a real target, verify the installed scanner path, required permissions, reception and expiry. No broad background scanner is enabled. |
| BLE sensor proxy | **Not installed; physical test pending.** Android proxy candidate and compatibility requirements are documented. | Verify an ARMv7 artifact, select one real sensor, enable authenticated/encrypted transport where supported, then test screen-off, reconnect and reboot. |
| Bluetooth speaker receiver | **Observed profile + implemented settings entry.** Both ROM inventories expose A2DP sink service; a fixed action opens Bluetooth settings. | A selected nearby phone must pair and produce audible sound. Reconnect, volume and call/audio-focus recovery are untested. |
| Music/radio/OTT | **Existing + installation parity.** VLC and native OTTPlay are installed on both; existing VACA music and fixed TV/player actions remain. | Test a real stream and Stop/Home on each device. Installation does not prove codec support or absence of stalls. |
| Photo/info frame | **Implemented / optional.** Up to twelve explicitly configured same-directory JPEG/PNG/WebP images, bounded cache and readable clock; room-state information cards. | No album is enabled by default. HA `/local` is publicly readable; use appropriate images. A calendar-feed integration is not supplied. |
| Local room camera | **Existing / scoped.** Existing camera application/pilot remains separate from outdoor-camera viewing. | Explicitly start and stop a stream, verify camera release before Jitsi, and retain privacy controls. No always-on recorder is added. |
| Sound-event detection | **Not implemented.** No extra microphone recorder or uncalibrated sound-pressure sensor is introduced. | Extend the existing VACA PCM pipeline if needed; define event labels, false-alarm tests, privacy behavior and CPU budget first. |
| Physical shortcuts | **Not implemented as new key remapping.** Existing hardware volume/privacy functions are retained; room actions are available through the panel/HA. | A foreground-only gesture or selected remote can be added after key behavior is measured without disrupting normal volume or mute. |
| QR/visual workflows | **Not implemented.** No scanner application or continuous camera workflow is enabled. | Select a deliberate scan use case, verify camera ownership and return to the previous room mode. |
| USB/Bluetooth accessories | **Physical test pending.** No keyboard, audio adapter or other accessory has been enumerated in this delivery. | Check actual host mode, available power, driver/profile and recovery with the intended accessory. Generic feature flags are insufficient. |
| On-device AI server | **Not enabled; server offload retained.** The Show remains an input/display/wake-word/media endpoint. | Heavy ASR, LLMs, analytics and transcoding belong on the existing server infrastructure; no new model server competes for approximately 974 MiB RAM. |

## Protocol and administration extensions

| Requested route or protocol | Delivered state | Boundary and next step |
| --- | --- | --- |
| Multiroom Sendspin | **Installed / pending.** SendspinDroid 2.0 on both devices; fixed launch/cleanup route and pinned artifact record. Observed MA 2.10.8 passes the application's minimum server version gate. | Complete normal server setup, then test decode, audible synchronization, screen-off continuity and release for calls. No synchronization result is claimed. |
| Snapcast alternative | **Not installed.** Remains an alternative if the Sendspin trial exposes a concrete need. | Avoid running duplicate background music clients without an acceptance reason. |
| AirPlay into the home audio system | **Not enabled.** A Music Assistant server-side receiver remains the documented route to accepted players. | Configure and test the server plugin only after a Show player is accepted. This does not create a native Android AirPlay receiver. |
| NAS music/video | **Client installed; launch implemented.** VLC is available on both and a fixed Library action opens its browser. | Configure the intended SMB/UPnP/DLNA source inside VLC and test credentials, throughput, codec and Stop/Home. No share credentials are published or automatically imported. |
| MQTT telemetry / commands | **No new Android agent.** Existing VACA/HA entities supply current telemetry; typed room scripts supply commands. | Add a broker client only for an unmet integration need, with topic authorization, expiry and acknowledgements. No retained start/call command is introduced. |
| Remote screen control | **Implemented; device screen test pending.** Checked, bounded scrcpy session, 960-pixel size limit, 15 fps and no audio capture by default. | Use a permitted direct-LAN route or an explicitly allowed SSH tunnel. A health read does not establish screen/input acceptance. |
| SSH and SFTP on Android | **No new daemon.** Existing authenticated host administration plus scoped ADB file transfer handles current tasks. | Bundled SSH binaries do not imply a configured or running SSH server. The NAS currently prohibits the attempted forwarding route; direct LAN mode is explicit, not a silent fallback. |
| Telnet | **Not enabled.** No working Telnet service was established by the inventory. | It adds no needed function beyond the existing administration path. There is no claim that a missing PATH entry proves every possible binary is absent. |
| VNC / RDP | **Not installed.** scrcpy is the implemented Android screen route. | A separate client/server role would need a concrete destination, authentication and screen-size acceptance. SSH installation alone supplies neither protocol. |
| Camera RTSP / ONVIF roles | **No new server.** Keep the existing explicit camera pipeline. | A camera permission grant is not an RTSP or ONVIF implementation. Verify any future protocol endpoint and its teardown independently. |
| APK and file maintenance | **Implemented.** Package/hash/API/ABI checks, ordinary same-signer updates, dedicated Downloads transfer directory and private output receipts. | Android still enforces signing and app permissions. Shared-storage transfers are not app-private backups; this is not a firmware conversion tool. |

## Hardware and permission boundaries

The measured runtime is Android 11 / API 30 with a 32-bit ARMv7 application ABI.
Only **LIGHT** is present in the actual sensor inventory. Generic feature flags
do not establish working accelerometer, compass, proximity, room temperature or
humidity sensors. The thermal HAL is not ready; a zero status is not a temperature
measurement. IR, Zigbee, Thread and a new Matter-controller radio role are not
supplied by this work.

No new root access, firmware unlock, blanket permissions, accessibility service,
notification listener, permanently discoverable Bluetooth mode, camera recorder
or public debug listener is added. The existing legacy ADB LAN connection remains
unencrypted on its LAN hop. The administration tool verifies an exact device and
does not bypass the user's Android debugging approval.

## How to finish acceptance

1. Activate the checked HA packages in the coordinated change window. Load r13
   on both Shows and verify every selected room binding before marking the panel
   live.
2. Exercise manual and automatic camera viewing, Stop/Home, one announcement,
   timer completion/reconnect and native-call rejection. Keep the current voice
   configuration and manual brightness baseline.
3. Finish Show-two administration acceptance through its authorized route, then
   test a bounded scrcpy session and one disposable shared-storage transfer.
4. Configure Sendspin through its normal UI/discovery. Accept real playback and
   resource handoff before advertising multiroom or AirPlay support.
5. When the selected phone, beacon or accessory is available, perform that
   physical test and update the corresponding row independently. Unsupported or
   unimplemented rows remain explicit rather than being inferred from app icons.

Detailed implementation contracts:
[room panel](room-panel.md), [session policy](room-session-policy.md),
[remote administration](remote-admin-tools.md),
[existing endpoint](remote-endpoint.md),
[native SIP](../integrations/show5-sip/README.md), and
[Android baseline](android-and-home-assistant.md).

Raw device identities, credentials, private server mappings, screenshots and
deployment receipts stay in ignored private storage. This public register records
capabilities and their acceptance scope without publishing household inventory.

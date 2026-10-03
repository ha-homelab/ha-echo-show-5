# Home Assistant intercom for a converted Echo Show 5

This optional integration adds bounded talkback, an optional audio reply and an experimental WebRTC call room to a converted **Echo Show 5 Gen2 / cronos**. It uses Android IP Camera 0.14.0, VACA 0.13.4, the Home Assistant Companion minimal app and HA-authenticated WebSocket commands. No PBX or additional media server is required for this implementation.

**Validation checkpoint:** 45 Python tests, 22 inert frontend tests, 17 readiness tests, two duplicate-import checks and five call-panel tests pass. The separate project suite has 83 tests. Imports and configuration schema were checked in **HA Core 2026.9.1**. Live bounded audio transport, membership guards, service/microphone restoration and synthetic video signaling passed the checks below. Camera availability and fresh MJPEG frames recovered after an attended Android reboot and manual app startup; isolated WebView capture also passed. **A complete WebRTC call and physical audibility remain unverified.**

## Tested results

The following checks were performed on the converted device and installed HA instance; they are separate from the offline tests:

- **Talkback transport:** the real handler accepted 8,820 zero PCM bytes, equivalent to 100 ms of silence. A second authenticated connection could neither end the active lease nor acquire another one. The upload restored the prior mute state before returning, and a subsequent explicit end was idempotent. No human audio was recorded and no speaker audibility was established.
- **Bounded Listen:** a one-second request returned 88,200 PCM bytes at 44,100 Hz with nonzero samples, held only in memory. Afterward the camera app's microphone permission was denied again, one VACA recorder was active, software mute was off and the lease was idle. This establishes capture/cleanup, not intelligibility or playback quality.
- **Synthetic video lifecycle and membership guards:** live WS checks passed for replacing a caller membership on the same connection, rejecting the old member's actions/signals, surviving an obsolete unsubscribe, relaying inactive offer/answer data, rejecting a stale call ID, receiving restoration events and returning to the previous mute state. All ten checks passed. These clients created no real WebRTC media; the results establish protocol behavior and service/microphone cleanup, not fresh camera frames.
- **Camera recovery:** an answered call reported `NotFoundError` while the browser enumerated audio input/output only and Android's camera service reported zero cameras. After an ordinary reboot with hardware privacy off, both the camera service and public camera API reported one camera. Manually starting the camera app and Companion returned two different fresh authenticated MJPEG frames, held only in memory. This demonstrates manual recovery; it does not identify the cause of the earlier camera loss.
- **Isolated WebView capture:** separate `getUserMedia` checks acquired audio in 977 ms, video in 1,376 ms at 640×480, and both in 1,488 ms. The exact production constraints also acquired both in 1,450 ms at 640×480. These establish local media acquisition after camera recovery, not peer connectivity, received media or sound heard by a person.
- **Actual browser video:** after repairing the Companion endpoint, the lightweight panel loaded, authenticated and joined the room. It received an incoming call and Answer was selected on the Show. Backend handoff completed; the caller acquired media and submitted an offer. The Show's debugger then timed out, and no media between peers was confirmed. This does not identify the cause. Video remains experimental and unverified.
- **Final cleanup after that attempt:** the backend returned to idle without recovery pending. Independent checks found different fresh MJPEG frames, the camera app's microphone permission denied and one VACA recorder active. These establish the recovered camera/microphone baseline, not physical audibility or wake-word acceptance.
- **Final daily-use pilot state:** `video_enabled: false` and `call_panel: false` were applied, configuration validation passed, and one normal HA restart completed. Video cards and the call panel were absent; the audio card remained. Companion home reconnected automatically, and VACA, Android Debug Bridge and camera entities were idle. Checks confirmed one VACA recorder, denied camera microphone permission, the retained Always-on Display override and two different fresh MJPEG frames. A test announcement completed, restored its volume and returned to idle/unmuted; physical audibility remains unverified. USB is not required for this running Wi-Fi session, but the Android-reboot recovery limitation below still applies.
- **Related controls:** an announcement action completed and restored its previous volume, but physical sound was not confirmed. The dedicated home dashboard rendered at 960×480. With the original Android setting backed up and `doze_always_on=0`, key event 223 produced display OFF after five seconds while wakefulness remained `Dozing`; key event 224 restored display ON and `Awake`. This verifies display-state transitions, not deep CPU suspend or long-term voice operation with the screen off. See [the setting change and rollback](../../docs/android-and-home-assistant.md#screen-sleep-and-always-on-display).

Network ADB was lost during that ordinary reboot and restored through the already trusted USB host. The Always-on Display override persisted and VACA autostarted, but camera and Companion startup was manual. Camera Start on Boot remains off, so unattended intercom recovery is not established. No new physical wake-word or audibility acceptance was performed. A successful action or signal exchange does not substitute for those checks.

## Functionality and limits

- **Talkback:** record up to ten seconds in the sending browser, then send the clip to the Show. The card converts it to PCM16 little-endian mono at 44,100 Hz; HA submits the bounded payload to the camera app's protected `/audio/upload`. VACA is muted during the operation and its previous software-mute state is restored afterward. The camera app needs no Show microphone permission for playback. This is record-then-send, rather than a continuous push-to-talk stream.
- **Optional Listen:** capture five seconds from the Show for playback in the requesting browser; the API allows at most ten seconds. This temporarily restarts the camera app with microphone permission, opens one `/audio` subscriber, then closes it, revokes that permission, restarts the camera service and returns Companion home. An existing video stream is interrupted. `listen_enabled` defaults to `false`.
- **Optional audio/video call:** one caller and one receiving card exchange WebRTC signaling through HA. An explicit **Answer** acquires an exclusive resource lease, mutes VACA and stops the camera app before browser media acquisition. Calls are limited to two minutes. End, disconnect or expiry stops browser tracks and invokes restoration. The backend force-stops the known Companion call host, restarts the camera service, waits for its authenticated control endpoint, returns Companion home and restores the previous VACA mute state. It does not validate fresh video frames. `video_enabled` defaults to `false`.
- **Optional lightweight receiver:** `call_panel: true` registers the administrator-only `/show5-call` panel with just a Home link and the existing receiving card. It avoids loading Lovelace dashboard resources for the receiving view. The default remains the `/echo-show/receive` subview; the home dashboard and caller card are independent of this option.

Talkback and Listen are half duplex. The WebRTC path requests browser echo cancellation and bidirectional media, but physical echo behavior and intelligibility need attended testing. Audio is held in memory by this implementation; it does not write audio files. Do not enable WebSocket payload debug logging during use, because transport logging could retain base64 audio.

The existing [HA MJPEG camera](../../docs/camera-and-intercom.md) remains the ordinary video view. A working camera preview does not establish a working call.

### Daily-use configuration without experimental video

To finish video testing and retain dashboard, camera, voice and separately configured audio controls, set both fields in the existing integration configuration:

```yaml
video_enabled: false
call_panel: false
```

End the active call and verify cleanup first. Remove the video-call cards and navigation buttons from the daily dashboard, validate configuration, restart HA once and check that the existing device connections return. This does not remove the camera integration, VACA or the talkback/listen controls; keep their individual settings and acceptance limits. After the restart, verify idle intercom status with no recovery pending, fresh authenticated camera frames, camera microphone permission denied and resumed VACA capture. A successful restart does not establish unattended Android reboot recovery or long-term reliability.

## Access and session ownership

Every intercom WebSocket command requires a **HA administrator** who can control the configured VACA mute entity. Permission to toggle that switch alone is insufficient. This pilot is unsuitable for exposing call controls to untrusted users. Caller-driven HA service actions carry the user's context; startup restoration is internal recovery of the persisted lease.

A lease belongs to a user **and a specific WebSocket connection**. Each video subscription also receives its own opaque `peer_id`: room actions and signaling must match that membership on the same connection. A removed card's late End or unsubscribe cannot act on a replacement card's membership, even when both share HA's browser socket. Audio leases normally last 45 seconds; video leases last at most 120 seconds. The recovery journal is written before resource changes. Cross-connection operations, oversized PCM and malformed encoding are rejected. Failed restoration keeps the journal, blocks new acquisitions and raises a HA notification. Startup recovery waits for `homeassistant_started`; the administrator can retry through **Recover** after repairing device connectivity.

Two restoration limits remain:

- **Newer software-mute choices are not reconciled.** Cleanup replays the mute state saved before the session, including during delayed recovery. If an operator changes VACA software mute during a call or while recovery is pending, restoration can overwrite that newer choice. Confirm the desired software-mute state again after End or Recover finishes. The hardware privacy control is separate.
- **Listen's temporary permission depends on reachable ADB for revocation.** If connectivity fails after `RECORD_AUDIO` is granted to the camera app, the permission can remain granted beyond the lease deadline until device access and recovery succeed. Closing this integration's audio subscriber does not revoke Android permission. The journal and blocked sessions expose failed cleanup, but provide no device-local expiry of that permission. This does not establish continued recording; independently verify revocation after restoring access.

The receiving **Answer** button is enabled only after membership and an incoming call. **Call Show** requires an idle membership and stays disabled while ringing, connected or restoring. A `restored` event follows the backend's command/control-endpoint and mute checks; it does not establish usable camera frames. `ended` alone only says that cleanup started. An unjoined card never sends End when removed.

**Protocol update:** `room_join` keeps its empty result and emits `{event: "joined", role, peer_id}` on the subscription. Every `room_action` and `signal` requires that 32-character lowercase hex `peer_id`; `signal` additionally requires the existing `call_id`. Stale membership commands fail with `intercom_failed`; missing/malformed IDs fail schema validation. Occupied roles are not replaced automatically. Deploy the backend and JS together, restart HA, and fully reload both call endpoints when upgrading an earlier pilot.

The receiving card's `role: show` is a configured role, **not device authentication**. Any authorized administrator can occupy it. An Answer proves an authorized receiving endpoint responded, not that the physical Show answered. Keep the receiving card on the intended device's dedicated subview or optional receiver panel.

The browser uses no configured STUN/TURN server. This does not enforce private-network destinations in arbitrary authenticated SDP. Start with two browsers that have direct local connectivity; remote-network reachability, NAT traversal and relay operation are not established.

Camera credentials and the SHA-256 certificate pin remain in HA. Requests use fixed camera paths, reject redirects and verify the pinned TLS certificate. Clients cannot supply camera destinations, app/package names or arbitrary ADB commands. The frontend JavaScript is a normal static HA resource and contains no secrets; media and signaling use authenticated WebSocket handlers.

## Prerequisites and baseline

Use the [Android setup guide](../../docs/android-and-home-assistant.md), [VACA guide](../../docs/vaca-private-wakeword.md) and [camera guide](../../docs/camera-and-intercom.md) first. Confirm:

- Companion is authenticated to HA over a secure browser context and the protected camera endpoint is reachable from HA.
- The correct VACA mute switch is known and reports `on` or `off`.
- Camera video running, camera microphone permission denied and Companion in the foreground are the intended baseline. Listen/video cleanup restarts the service and restores permissions/mute; separately verify fresh frames. It does not snapshot arbitrary prior app, permission or camera-off choices.
- For Listen or Video, core **Android Debug Bridge** provides `androidtv.adb_command` for this exact converted device. Verify the full device identity before assigning that entity. The built-in probe checks `cronos` and shell UID 2000; it does not distinguish two different cronos units.
- For Video, both endpoints have microphone/camera permission, including Android Companion permission and the WebView/site permission. Loading a card does not itself request media; Answer begins acquisition.

The fixed Android packages are `com.github.digitallyrefined.androidipcamera` and `io.homeassistant.companion.android.minimal`. The camera activity is `.activities.MainActivity`. A full Companion installation uses a different package and is not a drop-in match for these fixed actions.

**Reboot limitation:** the tested network ADB setup is a runtime, authenticated connection. It **did not return after an ordinary Show reboot**; the trusted USB host had to enable TCP5555 again before HA reconnected. Follow the [manual recovery procedure](../../docs/camera-and-intercom.md#manual-recovery-after-an-android-reboot). Listen/video check the adapter before taking the mute lease, but a connection lost after handoff can still leave restoration blocked until access returns. Talkback does not use ADB. **Camera Start on Boot remains off.** Neither the integration nor its recovery journal establishes unattended device-reboot recovery; deliberately configure and test both dependencies before relying on that behavior.

### When Android has no camera

Treat `NotFoundError` together with an empty Android camera inventory as a camera-availability diagnostic, not proof of a denied browser permission. Inspect the physical camera shutter/privacy controls and the [ROM's camera/privacy behavior](../../docs/android-and-home-assistant.md#rom-capabilities-and-limitations). Through the already identity-verified Android adapter, check Android's camera-service inventory, then compare browser media-device enumeration before retrying a call. The observed zero-camera condition recovered after a reboot with hardware privacy off; this does not identify its cause or establish a permanent hardware fault.

An authenticated `/control/status` response can report `streaming: true` even when no camera is available. That flag and a running app prove neither capture nor fresh frames. After the camera reappears, require newly received JPEG frames from the authenticated stream and a working camera preview; do not count a cached HA still. Only then repeat browser media acquisition and an attended video call. Avoid changing unrelated permissions or repeatedly restarting services as a substitute for checking physical availability.

The later isolated WebView checks successfully acquired 640×480 camera input with the production constraints. A historical Camera1/API label alone therefore does not establish Camera2 or WebRTC incompatibility on this device. Separate current camera availability, `getUserMedia` completion, signaling and received media when diagnosing a call.

## Install

1. Back up any existing integration, resource and configuration files. On the host where the HA configuration directory is accessible, copy the component and card from this repository. Replace the directory placeholder with that installation's actual configuration directory:

   ```bash
   HA_CONFIG_DIR=/path/to/your/home-assistant/config
   mkdir -p "$HA_CONFIG_DIR/custom_components/show5_intercom" "$HA_CONFIG_DIR/www"
   cp integrations/show5-intercom/custom_components/show5_intercom/*.py \
     integrations/show5-intercom/custom_components/show5_intercom/manifest.json \
     "$HA_CONFIG_DIR/custom_components/show5_intercom/"
   cp integrations/show5-intercom/www/show5-intercom-card.js \
     integrations/show5-intercom/www/show5-call-panel.js \
     "$HA_CONFIG_DIR/www/"
   ```

2. Merge [configuration.example.yaml](configuration.example.yaml) into the existing HA configuration. Do not replace the whole configuration. Replace its mute/ADB entity placeholders with verified entity IDs and initially keep both optional modes `false`. Talkback can omit `adb_entity` if Listen/Video are disabled. The optional `call_panel` flag also defaults to `false` when omitted. Copy the current manifest with the component: it declares the required `frontend` dependency.

3. Define the four referenced entries in HA's private `secrets.yaml`: `show5_camera_origin`, `show5_camera_username`, `show5_camera_password` and `show5_camera_certificate_sha256`. The origin is the camera's HTTPS scheme/host/port only, with no credentials or extra path. The pin is 64 hexadecimal characters representing the camera certificate's SHA-256 digest. Obtain and verify that certificate through a trusted device connection; do not trust an unexpected replacement certificate automatically. Never place these values in a dashboard, the JS resource or this repository.

4. Validate HA configuration, restart HA normally and inspect integration setup errors. Add `/local/show5-intercom-card.js` as a **JavaScript module** under the dashboard resource settings. Reload the frontend after installation or a JS update.

5. Add a talkback card to an operator dashboard:

   ```yaml
   type: custom:show5-intercom-card
   ```

   Use **Status** before recording. A successful upload means accepted bytes; check physical sound separately. Cancelling before submission sends no clip. Already accepted playback cannot be recalled and is bounded to ten seconds.

6. Before enabling Video, ensure the return-home dashboard exists at the exact route `/echo-show/home`. On the caller's `calls` view, add:

   ```yaml
   type: custom:show5-video-call-card
   role: caller
   ```

   By default the receiver uses `/echo-show/receive`. Make `receive` a **subview** of that `echo-show` dashboard, and put this card on it. Alternatively, use the lightweight panel described below instead of the receiving subview.

   ```yaml
   type: custom:show5-video-call-card
   role: show
   ```

   If the receiving endpoint is absent, Call wakes the Show and opens its receiver view, allowing at most 45 seconds for the endpoint to connect. Incoming calls require Answer and expire unanswered after 30 seconds. A returned Android intent or WS connection does not prove a rendered, usable card.

7. Enable optional modes individually only after checking the respective device permissions and restoration sequence; validate/restart HA after changing this YAML configuration. Complete the attended checks below before describing either mode as operational.

The [portable HA package](../../examples/home-assistant/README.md) provides separate announcements, media, display and navigation wrappers. The [native dashboard template](../../docs/show-dashboard.md) remains a conservative starting point; its inactive Calls placeholders are not automatically replaced by installing this custom integration.

## Optional lightweight call receiver

This option provides a small HA custom panel at **`/show5-call`** without the receiving dashboard's Lovelace resources. It imports `/local/show5-intercom-card.js` relative to `/local/show5-call-panel.js`, so copy **both files into the same HA `www/` directory** as shown above. Keep the normal card resource for the caller and talkback cards; the panel module is registered by the backend, not as an additional Lovelace card resource. Duplicate module evaluation is guarded against redefining custom elements.

Inside the existing `show5_intercom` configuration, with its verified `adb_entity` and other private settings retained, enable:

```yaml
video_enabled: true
call_panel: true
```

Validate the configuration and restart HA. Panel registration requires both enabled Video and a configured Android Debug Bridge adapter; an existing `show5-call` route is rejected rather than replaced. The route uses HA's **`require_admin: true`**, has **no sidebar entry**, and contains no credentials. Open it by URL on the intended Show using its authorized administrator session. The existing WebSocket authorization and explicit Answer requirement still apply.

When a call needs to open an absent receiving endpoint, this mode **force-stops and starts Companion** at `/show5-call`. It starts a fresh WebView instead of navigating the current dashboard in place. With the flag omitted or `false`, the existing `/echo-show/receive` navigation remains unchanged. Both modes restore Companion to `/echo-show/home` after cleanup; the panel's Home link uses that same fixed route. The existing home dashboard does not need to be replaced.

The panel reuses `show5-video-call-card` for membership, media ownership and cleanup. Leaving the panel removes that card and invokes its normal cancellation; there is no second media owner or separate hangup implementation. It does not grant microphone/camera permission, start a call automatically or establish successful peer media. Validate a complete attended call separately. To return to the default receiver, set `call_panel: false`, restart HA and use the configured `/echo-show/receive` subview.

## Optional Companion readiness workaround

Companion Android **2026.8.4** has a ten-second native frontend-handshake timeout. On this Show, a saved log recorded the connection message more than eleven seconds after the initial bridge configuration. A working HA WebSocket can therefore coexist with the native connection-timeout overlay. This timing is evidence for a delayed handshake; it does not classify every connection error as the same problem.

Check [Companion endpoint reachability](../../docs/android-and-home-assistant.md#repair-an-obsolete-companion-server-address) first. A separate pilot investigation confirmed an obsolete external hostname returning NXDOMAIN; updating the existing server's External URL to a verified same-instance HTTPS/WSS endpoint retained authentication. That DNS outage and the earlier frontend timing observations are distinct findings. The helper below cannot repair an unresolved hostname, TLS failure or failed authentication, and the address repair alone does not validate a video call.

For this specific slow-start case, the same JS resource includes an opt-in, zero-size helper. Add it to each relevant `echo-show` view only after confirming the frontend underneath the overlay really renders and connects:

```yaml
type: custom:show5-readiness-card
enabled: true
```

The helper runs only in the top-level `/echo-show` dashboard, checks the authenticated HA user, connection, config and states, requires the frontend launch screen to be gone and an enclosing Lovelace view to have rendered with nonzero dimensions, then waits two animation frames and rechecks. It sends `frontend/loaded` through the existing `hass.auth.external.fireMessage` helper once per document. It requests no camera/microphone permissions, sends no authentication data and has no raw bridge fallback. Readiness retries stop after thirty seconds or immediately when the card is removed. Without `enabled: true`, it does nothing.

This is a **version-scoped compatibility workaround**, not a stable custom-card API. The message is implemented in [frontend 20260826.6, as pinned by HA Core 2026.9.1](https://github.com/home-assistant/frontend/blob/18f79dfc919e2019102c4fde0606fdb449f4cc15/src/layouts/partial-panel-resolver.ts#L266) and accepted by [Companion 2026.8.4](https://github.com/home-assistant/android/blob/697f91828d8cc19c64bb408dacf5859450f2b92f/app/src/main/kotlin/io/homeassistant/companion/android/frontend/FrontendViewModel.kt#L1210). Its native handler clears only the loading state or that specific handshake-timeout overlay; SSL, authentication and security-block states are not changed. The [transport is documented](https://developers.home-assistant.io/docs/frontend/external-bus/), but the current public message reference does not list this event. Revalidate after frontend or Companion updates, and remove the card when the workaround is no longer needed. Dispatch has no acknowledgement: verify that the native overlay disappears and the actual page remains usable.

## Acceptance and recovery

Verify administrator/nonadministrator handling, busy-session rejection, cross-connection ownership and preservation of an initially muted VACA state. A short silent PCM smoke test can establish handler dispatch, authenticated camera transport and restoration without recording anyone; it cannot establish audibility.

For an attended talkback test, confirm speaker output, temporary VACA mute and resumed VACA listening. For Listen, verify one camera-app recorder during capture, camera microphone permission denied again afterward, resumed VACA capture, fresh camera video and Companion home. Do not treat a successful service return as proof of these physical states.

For Video, verify both pictures and intelligible audio, explicit Answer, denied/missing browser permission, End, caller-tab closure, receiver-WebView loss, the two-minute limit and network interruption. Check fresh camera video, Companion home and the original VACA mute state afterward. A signaling-only test without media cannot replace these checks.

The call card keeps its first failure as `lastFailure: {stage, code}` and preserves it in the status through hangup. It logs `SHOW5_CALL_FAILURE <stage> <code>` using fixed stage labels and allowlisted DOM/HA error codes; unknown errors become `UnknownError`. Fixed `SHOW5_CALL_STAGE` milestones distinguish ready-event receipt, camera/microphone request, completed capture setup, peer creation, offer/answer submission and connection. Exception messages, addresses, SDP, candidates and media are never included. Inspect fresh timestamped markers in the Android log; debugger attachment can replay older console entries. `media_requested` without `media_acquired` means media acquisition has not completed, rather than proving a network failure.

Answer immediately displays Preparing, and successful local media acquisition displays Connecting. The connection deadline is **45 seconds after local media acquisition**, increased from twenty seconds for the slow Show hardware. The separate **120-second backend video lease** and eight-second disconnected deadline remain unchanged; new calls reset the prior failure. `connection connection_timeout` identifies the connection deadline. Cancellation, backend expiry and failure still stop local tracks and request restoration; a failed restoration request remains explicitly unconfirmed in the UI. More startup time does not establish successful WebRTC media.

The video card stops local media and discards its room membership when HA disconnects. It makes one fresh join attempt when the connection returns, with automatic subscription replay disabled. A rejected join stays paused until **Retry room** or a later reconnect; ordinary HA state updates do not flood the room with retries. A new server-issued membership is required before calling or answering.

Backend logs use fixed `SHOW5_BACKEND_STEP` phase, outcome and error-category labels. Each Android action is bounded to twelve seconds; software-mute service execution and state confirmation each have an eight-second limit. Failed steps are warnings. Set the `custom_components.show5_intercom` logger to `info` temporarily to include begin/success markers; no command text, exception messages, addresses or credentials are logged.

Also test a HA restart with a saved lease. If Status reports recovery required, repair the adapter/device first, then use **Recover**. New sessions should remain blocked until restoration succeeds. Keep the recovery journal; deleting it does not restore a microphone, permission or camera owner.

To remove the integration, end any session and confirm the baseline first. Remove the YAML stanza, cards, module resource and component directory, then restart HA. Preserve the journal until resource restoration has succeeded.

## Offline validation

The **45 Python tests and 22 inert frontend tests** cover payload limits, exclusive/owner-bound leases, cancellation and expiry, failed preparation/restoration, persisted recovery, administrator checks, caller context, room cleanup and late browser permission/subscription completion, including an incoming call delivered before subscription setup finishes. Backend diagnostics have bounded service calls/readbacks and redact private values. Frontend checks also cover failure preservation after cleanup, negotiation errors, diagnostic redaction, the bounded connection timeout, queued signaling during media acquisition and controlled retries after HA reconnection. They do not contact HA or devices. Run from the repository root with Python 3.11 or newer and Node.js:

```bash
python3 -m unittest discover -s integrations/show5-intercom/tests -v
node integrations/show5-intercom/tests/test_frontend.cjs
node integrations/show5-intercom/tests/test_readiness.cjs
node integrations/show5-intercom/tests/test_duplicate_import.cjs
node integrations/show5-intercom/tests/test_call_panel.cjs
node --check integrations/show5-intercom/www/show5-intercom-card.js
python3 -m py_compile integrations/show5-intercom/custom_components/show5_intercom/*.py
```

Actual HA Core 2026.9.1 import/schema validation supplements these tests. Live media and recovery evidence must be recorded separately.

An additional **17 inert readiness tests** cover opt-in, offline/missing-auth data, missing native helper, wrong dashboard/frame, incomplete rendering, two-frame rechecks, removal, bounded retries and one signal per document. They do not establish live Companion recovery.

Two duplicate-import checks and five inert panel tests cover repeated module loading, receiver composition, forwarding HA state and card lifecycle ownership. The Python suite includes optional panel registration, required settings, administrator restriction and route collision handling. These checks do not establish a working real call. The separate root-level tooling suite contains **83 tests**.

## Upstream references

- [Pinned Android IP Camera server](https://github.com/DigitallyRefined/android-ip-camera/blob/4a723736d207f3a44bffb3d99417c9b30309f993/app/src/main/kotlin/com/github/digitallyrefined/androidipcamera/helpers/StreamingServerHelper.kt) and [browser implementation](https://github.com/DigitallyRefined/android-ip-camera/blob/4a723736d207f3a44bffb3d99417c9b30309f993/app/src/main/assets/index.html): protected audio paths, subscriber lifetime and idle playback watchdog.
- [HA permissions and caller context](https://developers.home-assistant.io/docs/auth_permissions/#the-context-object), [HA Core 2026.9.1 AndroidTV service](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/androidtv/media_player.py) and [WebSocket decorators](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/websocket_api/decorators.py).
- [Pinned VACA source](https://github.com/msp1974/ViewAssist_Companion_App/tree/65906aebffd2f39772773b44729b22fd022a1f3c): software mute and recorder behavior. Recorder activity alone does not prove acoustic input or wake-word recognition.

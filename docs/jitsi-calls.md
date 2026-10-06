# Optional native Jitsi calls

This pilot uses the stock **Jitsi Meet Android app** with an operator-controlled Jitsi server. It runs separately from Companion and the experimental HA WebRTC card. The pinned F-Droid build supports Android 11 ARMv7 without installing Google Play Services. HA coordinates camera/microphone handoff and restoration; the Jitsi server handles the conference.

**Validation scope:** an attended two-party native Jitsi call now passed received-video checks in both directions. The Show displayed the remote participant's moving synthetic video; the caller decoded 141 Show camera frames and received 61,873 audio bytes from the Show. ICE and DTLS connected on both sides. Before this device test, two Chrome clients exchanged synthetic audio/video for 60 seconds, decoding 811 and 714 inbound video frames. The bridge reported no queued packet drops or SRTP failures during the successful tests, and HA continued responding to authenticated configuration requests during the native call. Physical audibility, intelligibility, echo behavior and wake-word accuracy remain unverified.

Explicit **HA End passed after the successful media test**: the integration reported no active session or recovery pending, and the Jitsi process was absent. The camera returned two different fresh MJPEG frames with microphone permission denied. One unsilenced VACA recorder was active with software mute off, and Companion home visibly rendered with a live authenticated HA WebSocket confirming the server was running. After both participants closed, the bridge had no participants or receiver queue drops. This validates the observed handoff and restoration, not long-term recovery or physical sound quality. Keep the existing [camera](camera-and-intercom.md) and [VACA](vaca-private-wakeword.md) baseline available for recovery.

A later navigation check found that repeated Companion deep links retained three activities and WebViews. The remote navigation examples now clear the prior Android task; one activity and one WebView were observed after that launch. The home view eventually rendered, but cold loading and reconnecting were slow. A separate transient HA response stall also recovered without a restart; its cause remains unproven. The successful call and restoration checks do not establish sustained dashboard responsiveness.

A later check found VACA still running while microphone capture had stopped. Muting/unmuting and an app restart did not establish sustained recovery; a subsequent vendor audio-service restart restored an active recorder. The stop followed a no-text STT error, but source inspection did not establish that error as the cause. This remains an unresolved voice-reliability limitation. See the [audio diagnostic limitation](android-and-home-assistant.md#audio-diagnostic-limitation-on-the-tested-rom): one diagnostic triggered a separate HAL crash and must not be repeated.

> The second Show uses the newer [remote endpoint](remote-endpoint.md). Its
> operator-selected `jitsi_auto_join: true` policy opens the shared `/call` room
> with camera and microphone enabled, without prejoin/name entry. The attended
> prejoin defaults and 120-second lease below describe the separate intercom
> integration; the remote endpoint uses its own bounded lease (30 minutes by default).

## Reproduce the artifact

The [pinned manifest](../jitsi-artifact.json) selects **Jitsi Meet 26.0.0**, package `org.jitsi.meet`, version code `26000001`, **armeabi-v7a**, minimum SDK26 and target SDK35. This is the F-Droid signing lineage, distinct from the Play Store app. Do not replace an existing installation from another signing lineage without considering its retained data and settings.

```bash
python3 scripts/artifacts.py fetch jitsi
python3 scripts/artifacts.py verify jitsi
```

The expected file is `downloads/org.jitsi.meet_26000001.apk`: **17,356,331 bytes**, SHA256 **`1a993246979874704b873088fc535372f5b373b02f08d4827c4d2cac64e0a52d`**. Its APK signer SHA256 is **`41605393b4a087feb25d13e91f421c7d1a1a9146251fc2be992fc1b30b3181f6`**. Android SDK `apksigner` verified v2/v3 signatures; the signer, size and file digest matched F-Droid's authenticated package metadata. Repository authentication used SHA256-signed `entry.jar` and its exact index-v2 digest, with the certificate pinned to F-Droid's published repository fingerprint. No third-party APK mirror was used.

The download helper checks the pinned size, SHA256, `.apk` suffix and ZIP CRC. It does not run the APK, install it or repeat the separate signature/index audit. Downloads and raw verification evidence stay outside Git. Installation must target the independently verified Show; the existing `install-companion` action still installs only Companion.

## Server and permissions

Provide a working Jitsi server with a trusted HTTPS certificate and network access from the Show and the other participant. Test the intended room in an ordinary browser first, including any login or lobby policy. This guide does not deploy a server, configure TURN/NAT traversal or claim that reachability from HA establishes the Show's media path. Use the [official self-hosting guide](https://jitsi.github.io/handbook/docs/devops-guide/devops-guide-quickstart/) for the server side.

A connected conference can still fail to deliver media when its bridge cannot obtain enough CPU time. In this pilot, the original bridge host showed 75–77% CPU steal and queued RTP drops, without SRTP authentication or cipher failures. Moving the existing bridge to a healthy host with an enforced one-CPU cap restored received media. Check bridge scheduling and packet-drop counters alongside ICE/DTLS state; connection alone is not media acceptance.

Install the verified APK on the selected device and grant its **Camera** and **Microphone** permissions for attended call testing. These permissions belong to Jitsi; the ordinary Android IP Camera app keeps microphone permission denied. Calendar access is unnecessary for opening the configured room. Keep server addresses, room names, authentication and test media private.

The native app consumes device resources independently of Companion. The HA handoff therefore mutes VACA, stops Android IP Camera, stops Companion to free its WebView, wakes the Show and launches the fixed Jitsi package. Inspect the native Join screen and media controls before proceeding. The launch requests prejoin and initially muted audio/video; treat those as requested defaults until verified on the installed app, not an assurance that entering the app cannot activate media.

Source inspection at the [26.0.0 commit](https://github.com/jitsi/jitsi-meet/tree/3db92da369b921d73189dbcb55744f9f5459cac0) confirmed that the configuration whitelist accepts prejoin and initial audio/video mute settings, and the native prejoin feature defaults to enabled. Stock SDK call callbacks stay within the Android app; they do not provide HA with a termination event. The F-Droid route avoids a Google Play Services requirement; telemetry behavior requires separate review.

## HA configuration and operation

Use the updated [intercom integration](../integrations/show5-intercom/README.md), including its Python files and `services.yaml`. Inside its existing private configuration, retain the camera credentials, VACA mute entity and identity-verified Android Debug Bridge entity, and add:

```yaml
jitsi_enabled: true
jitsi_room_url: !secret show5_jitsi_room_url
```

The secret must be one fixed HTTPS host and a single plain room path, such as `https://meet.example.invalid/example-room`. That address is a placeholder. The validator rejects embedded credentials, query strings, fragments and caller-supplied launch parameters. Configure the actual room only in HA's private secrets. Native Jitsi does not require `video_enabled` or `call_panel`; those belong to the separate HA WebRTC experiment and can remain `false`.

Validate HA configuration and restart normally. The services accept **no parameters** and require an active HA administrator with control permission for the configured Show entities:

- **`show5_intercom.jitsi_start`** verifies the Android adapter and installed fixed package, then acquires the exclusive native-app lease and opens the configured room. Another audio/video session blocks acquisition. Explicit native Join and media choices remain an attended step.
- **`show5_intercom.jitsi_end`** force-stops the fixed Jitsi app, restarts the camera service, waits for its authenticated control endpoint, returns Companion home and restores the VACA software-mute snapshot. An authorized administrator may use End from another HA connection. It cannot end a different active intercom mode.

The [portable native-call card](../examples/home-assistant/jitsi-call-card.yaml) provides standard HA Start/End buttons and a placeholder room link. Place it on a separate **administrator-only dashboard** and replace the room link privately. Adding the card alone does not restrict dashboard access. The services independently require administrator authorization even if their buttons appear elsewhere. The card does not create a public room or confer intercom permission on nonadministrators.

The lease is fixed at **120 seconds including preparation**. Expiry begins restoration; it is not a guarantee that all remote cleanup finishes at exactly two minutes. Use explicit **HA End** when finished. Stock Jitsi termination events are local to its Android process; HA has no supported callback from the stock app. Leaving the room, pressing Android Back or entering Picture-in-Picture must not be treated as confirmation that HA restored the resources.

The existing [restoration limits](../integrations/show5-intercom/README.md#access-and-session-ownership) apply. ADB loss can block app shutdown/restoration, and replaying the saved software-mute state can overwrite a later operator choice. Keep the journal and use Recover after repairing connectivity; independently verify the intended final mute state. Running Wi-Fi operation does not need a USB cable. [Network ADB returned after an ordinary reboot](android-and-home-assistant.md#persistent-wi-fi-adb-on-the-tested-rom) without USB commands on the tested ROM; retain [trusted USB recovery](camera-and-intercom.md#manual-recovery-after-an-android-reboot) as a fallback. Camera boot start is off, and full unattended app recovery and power-loss behavior remain unverified.

## Attended acceptance

Verify an actual participant on each side, explicit native Join, the requested initial mute states, both pictures and intelligible audio. Then use HA End and require Jitsi to stop, Companion home to return, different fresh authenticated camera frames, camera microphone permission still denied and VACA capture restored to the intended mute state. A reachable camera control endpoint alone does not prove fresh video.

Separately test the 120-second expiry, user cancellation, connection loss and HA restart recovery before relying on unattended behavior. Preserve no household recordings or images in the public repository. Document transport success separately from physical audibility and echo behavior.

Artifact sources: [official Jitsi download routes](https://jitsi.github.io/handbook/docs/releases/), [F-Droid package](https://f-droid.org/en/packages/org.jitsi.meet/) and [F-Droid build metadata](https://gitlab.com/fdroid/fdroiddata/-/blob/master/metadata/org.jitsi.meet.yml). The signed source archive reference is recorded in the artifact manifest; this project has not reproduced the APK build.

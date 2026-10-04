# Remote controls for a second Show

This extension gives a separately identified Android Show a small set of Home
Assistant controls: return to its clock, show a named camera, open an attended
call, launch a selected player, or play a configured TV preset. Keep its target,
Android identity, helpers and VACA entities separate from the first Show.

These controls use the existing authenticated HA connection and a fixed private
mapping. The target name is a routing label, not a credential. An
administrator-only dashboard hides controls from ordinary accounts but is not
an authorization boundary for services. Authenticated household users may call
the generated HA scripts under HA's existing permissions. HA 2026.9.1 requires
administrator access for the raw WebSocket event subscription/fire APIs used
by the display adapter; this extension does not add a separate owner ACL.

## Private mapping

Copy [remote-endpoint.example.json](../examples/home-assistant/remote-endpoint.example.json)
to ignored private storage. Replace every placeholder before rendering:

- `prefix` identifies this endpoint's scripts/helpers and the display's
  `remoteTarget`. Use a unique value for each Show.
- `serial` is the complete independently verified Android serial. `adb_entity`
  must address that same device. A network address alone is not its identity.
- `vaca_mute_entity`, `vaca_media_entity` and `vaca_refresh_entity` must all belong
  to this endpoint's VACA entry.
- `clock_path` records the deployed versioned clock entry path. It is
  documentation-only in the renderer: configure the selected VACA entry's
  persistent home override separately and keep it pointed at that release.
- `jitsi_room_url` selects the operator's fixed meeting room; `ottplay_url`
  selects the existing OTT-play web/server installation.
- `app_ids` names the inspected installed packages. The example package names
  are not proof that those apps are installed. `ottplay_native` is optional.
- `tv_presets` maps short preset keys to fixed labels and approved HTTP(S) media
  URLs. Callers select a key; they do not supply an arbitrary TV stream URL or
  shell command.

The example deliberately uses nonworking `example.invalid` hosts. Keep real
endpoints, full serials, device bindings and any credential-bearing media URLs
out of Git and out of HA's public `/local` directory. Do not reuse another
player's device token or another Show's Android entity. A filled settings export
from either OTT application may contain provider credentials.

## Render and deploy

The renderer makes no HA or Android requests. From the repository root:

```bash
mkdir -p private/remote-endpoint
chmod 700 private/remote-endpoint
cp examples/home-assistant/remote-endpoint.example.json private/remote-endpoint/config.json
chmod 600 private/remote-endpoint/config.json
# Edit the private copy and replace every placeholder.
python3 scripts/render_remote_endpoint.py \
  --config private/remote-endpoint/config.json \
  --output private/remote-endpoint/show5-two-package.yaml
python3 scripts/render_remote_dashboard.py \
  --config private/remote-endpoint/config.json \
  --output private/remote-endpoint/dashboard.json
```

The output is JSON, which is valid YAML, written with mode `0600`. It must stay
inside this checkout's real `private` directory and the output file must not
already exist. Use a new private output filename when rendering a revision.
Review the generated fixed commands and device bindings before deployment.

Copy the reviewed output to HA's private packages directory using the existing
trusted configuration-access method. Include it through the installation's
existing `homeassistant: packages:` configuration, check HA configuration and
perform the normal reload/restart required for the new helpers and automations.
Do not replace the existing packages directory or configure another Show's
entities as a shortcut.

In the clock's private `config.js`, set `remoteTarget` to the same `prefix`,
alongside its existing camera mappings. Deploy a release containing the remote
event adapter and version **all five assets** plus its entry filename; see
[the clock guide](../integrations/show5-display/README.md#installation). Use
`Show5Auth.status()` to confirm the additional remote-event subscription after
VACA returns to the configured clock home. The target mapping in `/local` is
public, so it must contain no credential.

## Control and restoration contract

The generated command entry point is `script.<prefix>_command`. Its input fields
are `mode`, `preset`, `audio_media_id`, `lease_minutes` and `camera_seconds`.
The default app/media lease is 30 minutes, bounded to 120 minutes; a manual
camera command defaults to 120 seconds. This manual camera lease is separate
from the clock page's usual 30-second motion lease.

Supported modes are `home`, `stop`, `camera_front`, `camera_porch`, `music`,
`tv`, `ottplay`, `ottplayer` and `jitsi`; `ottplay_native` appears only when its
package is configured. Use HA Developer Tools → Actions to call the generated
script. For the example prefix:

```yaml
action: script.show5_two_command
data:
  mode: camera_front
  camera_seconds: 120
```

To open the separate OTT-play browser, use `mode: ottplay`; to open the branded
app, use `mode: ottplayer`. Either accepts a bounded `lease_minutes`. A fixed TV
preset uses:

```yaml
action: script.show5_two_command
data:
  mode: tv
  preset: channel_one
  lease_minutes: 30
```

For music, use `mode: music` with `audio_media_id` set to an approved audio
`media-source://` identifier or HTTP(S) stream. Music is sent to this Show's VACA
media entity, not to VLC or an OTT player. Alternatively,
`script.<prefix>_play_audio` exposes HA's media selector and passes the selected
audio item to the same command with a 30-minute lease.
`mode: jitsi` opens the configured room
at prejoin. `mode: home` and `mode: stop` use the same stop/return path. Do not
pass TV URLs, package names, shell arguments or private cleanup fields in these
service calls.

Camera and Home commands use the authenticated HA event path. The display
checks the configured target, command ID, expiry and allowed camera role.
Expired commands are ignored; repeated command IDs do not repeat an accepted
action. A permanent HA event automation records the acknowledgement in a helper,
so an immediate reply is not lost while the command begins waiting for it.
An acknowledgement means the renderer accepted the command, not that
video decoded or sound was audible. An intentional manual camera view has
priority over motion until its lease ends. Leaving or hiding the clock page
cancels that view; old events are not replayed when the page returns.

Application launches use fixed packages and URLs from the private mapping,
through the designated HA Android Debug Bridge entity. The generated identity
guard checks the full serial, `cronos` device and nonroot shell UID `2000`
before the fixed ADB action proceeds. Each operation also requires a fresh
success marker from the designated entity's ADB response. App installation is
checked before changing the active session. Do not replace these
wrappers with a caller-supplied ADB command or URL field.

Home is the explicit stop/return route. It ends the endpoint's bounded activity,
force-stops the app owned by that activity or stops its VACA music, and returns
to VACA's configured clock home. For Jitsi, it first stops Jitsi and restores
the microphone state saved before that call. Restoration means the previous
software-mute state, including an initially muted state; it does not blindly
turn listening on. Noncall player modes do not deliberately change the VACA
mute state. A lease provides
a fallback return timer, not proof that an app closed or that restoration
survived loss of the HA/ADB connection. Check readback after recovery rather
than extending a failed session indefinitely.

The package keeps an active mode, prior mute, pending mute-restoration flag,
session token and cleanup-attempt count. A failed stop retains ownership and
pending restoration. Cleanup errors can schedule up to three 60-second retry
opportunities; a new manual command resets that budget. Timer expiry, HA startup
and an eligible reconnect request cleanup; a saved
session token prevents an obsolete queued cleanup from stopping a newer session.
These are recovery mechanisms, not proof of recovery on an unreachable device.
The separate `script.<prefix>_refresh` presses only this endpoint's VACA Refresh
button; it is not a replacement for Home/Stop cleanup.

Opening Jitsi stops at **prejoin**. A person on the Show chooses whether to join;
opening the app must not answer or join automatically. Keep the explicit End/Home
path available and check microphone restoration afterward. See
[native Jitsi calls](jitsi-calls.md) for the separate call handoff and acceptance
requirements. Launching a room is not proof of a connected two-party call.

## The two OTT products

### Our OTT-play web and native apps

The existing OTT-play FOSS web/server UI can run in a **separate Android
browser**. This reuses the existing playlist/proxy infrastructure and can serve
the existing HTTP LAN sources. Open only the private configured player origin;
the browser has its own settings and does not inherit another device's provider
configuration. Its first launch may therefore need an intentional source setup.
The [public web demo](https://player.ottplay.here.now/) is a static HTTPS site,
not a proxy that automatically makes an HTTP-only LAN source playable.

Do not navigate the OTT page inside VACA's authenticated WebView: the reviewed
native external-auth bridge does not restrict requesting-page origin. Keep
VACA's clock home intact and launch the separately identified browser package.
The clock page's camera/event activity pauses while it is hidden; verify its
return and the separate VACA voice service afterward.

Our separate [OTT-play Native preview 0.2.1-preview.3](https://github.com/open-ott-play/ottplay-android/releases/tag/v0.2.1-preview.3)
uses Media3 playback and supports touch controls. The verified APK has:

- Package `play.ott.foss.nativeapp.preview`, version name `0.2.1-preview`, version
  code `3`, minimum API 26 and target API 36. ARMv7 is included.
- Launcher activity `play.ott.nativeapp.MainActivity`.
- Size **4,601,379 bytes**; SHA-256
  `afe42bac10fd903df2074242bae9870a561a6fef6ea13e6a1bce8b64bcfd932c`.
- Signer certificate SHA-256
  `2021e3c927fff7c42daf395beacbf0ef738c6d878a827091afb48ddaa32c4dd8`, matching the
  official release manifest. APK signature and archive CRC verification passed.

Its metadata is compatible with Android 11/ARMv7; that does not establish this
Show's decoder compatibility with every stream. The published preview accepts
**HTTPS sources only**, including redirects. An HTTP-only media
installation therefore uses the web route unless an appropriate HTTPS source
or the distinct native `full` variant is separately prepared. The preview's
manifest supplies app launchers, not a verified channel/playlist deep link.
Opening it does not select a programme or import settings.

The separate OTT-play Control Server controls a player that has already opted
in and connected. It is not an Android app launcher. Its command acknowledgement
is also distinct from confirmed playback.

### OttPlayer from ottplayer.tv

**OttPlayer** is a different product, with Android package `es.ottplayer.tv`.
The [official Android page](https://ottplayer.tv/soft/android) lists
`OttPlayer_6.0.9.apk`; the [Google Play listing](https://play.google.com/store/apps/details?id=es.ottplayer.tv)
documents its own account and playlist association. These settings are separate
from our OTT-play installations.

At the October 4, 2026 check, the official site's APK download returned
**HTTP 403** because its server could not read its access-control file. The
official `www` endpoint failed as well. No mirror APK was substituted. That
artifact's signature, hash, ARMv7 content and actual SDK requirements therefore
remain unverified; the website filename is not evidence of the latest Play
release. Keep the branded-app action unaccepted until a trusted APK is obtained,
verified and installed. Do not create an account, upload playlists or enter
credentials as part of an unattended launch check.

## VLC for fixed TV presets

The prepared VLC artifact is the official
[VLC Android 3.7.1 ARMv7 APK](https://download.videolan.org/pub/videolan/vlc-android/3.7.1/VLC-Android-3.7.1-armeabi-v7a.apk),
with its [published SHA-256](https://download.videolan.org/pub/videolan/vlc-android/3.7.1/VLC-Android-3.7.1-armeabi-v7a.apk.sha256):

- Package `org.videolan.vlc`, version `3.7.1`, version code `13070105`, minimum
  API 17 and target API 36; native ABI `armeabi-v7a`.
- Launcher activity `org.videolan.vlc.StartActivity`.
- Size **47,073,346 bytes**; SHA-256
  `a6a7f940e4bd190c9a70f3f0dc97c1c402c10200af20edac7a1d452b24abd8a0`.
- Observed signer certificate SHA-256
  `c8768d2cea0c4b622e419b4b4715981946821e4ebc035fb41776cad395a7f68e`.

The pilot installed this APK and confirmed visible TV playback. VLC's first
launch needs onboarding and video tips dismissed. On Android 11 its external
playback entry also checks storage-read permission, even for a network URL;
`READ_EXTERNAL_STORAGE` was sufficient, without granting all-files management.
See the [official launch implementation](https://github.com/videolan/vlc-android/blob/3.7.1/application/vlc-android/src/org/videolan/vlc/StartActivity.kt).
Use reachable, verified presets and check nested manifests/media segments, not
just HTTP 200. A loopback-only proxy catalogue must not be rebased to a LAN IP;
use the infrastructure's supported LAN listener and its own fresh catalogue.
Keep IPTV discovery, accounts and media-server administration outside the
endpoint's command fields.

## Acceptance on the intended device

On October 4, 2026 the second-device pilot verified:

- The r8 English clock/event adapter, manual Front and Porch WebRTC video with
  increasing decoded-frame counters, and Home/lease return to the clock.
- HA media-source audio reached `playing`; Stop and the original volume were
  restored after the bounded check. Physical audibility was not checked.
- Jitsi reached the attended **Join meeting** screen with microphone and camera
  off. Home stopped Jitsi and restored VACA's previously unmuted state.
- A configured LAN TV preset produced a visible picture in VLC and a playing
  Android media session.
- Both our native OTT-play preview and the separate web player opened. English
  was selected in the web player; provider/playlist setup remains separate.

The separate branded OttPlayer APK remains blocked by the official download's
HTTP 403. Its dashboard button is marked not installed, not advertised as ready.
No two-party Jitsi call, acoustic voice acceptance, Android reboot recovery, or
long-duration network-loss soak is claimed by these checks. The device had
observed Wi-Fi roaming disconnects during installation; a successful later
check is not proof those network interruptions have stopped.

First verify the exact endpoint identity and fixed configuration. Then check
Home, each camera and its return timer, each installed app's launch, and one
authorized media preset. Confirm actual picture and audible output separately
from service success. Test End/Home with VACA initially muted and initially
unmuted, and confirm return to the correct clock page without changing the
first Show. Complete an attended Jitsi Join/End test separately. Record network
loss, app restart and Android reboot results as different checks; do not infer
them from a successful manual launch. Keep evidence and filled mappings private.

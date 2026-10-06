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
- `jitsi_auto_join` is an optional boolean, default `false`. For an operator-selected
  shared room, set it to `true` to skip prejoin/name entry and start with camera
  and microphone enabled. Android permissions must already allow both. This is
  a deployment setting, not a caller-supplied action parameter.
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

To open our Capacitor Android client, use `mode: ottplay_native`. The separate
web route uses `mode: ottplay`; the optional third-party app uses `mode: ottplayer`.
Each accepts a bounded `lease_minutes`. A fixed TV
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
`mode: jitsi` opens the configured room using the deployed join policy.
`mode: home` and `mode: stop` use the same stop/return path. Do not
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

By default, opening Jitsi stops at **prejoin**. With `jitsi_auto_join: true`, the
Video call button instead joins the fixed room immediately with media enabled;
the rendered dashboard describes that behavior. The second Show uses this policy
with the operator's shared `/call` room, replacing its separate test room.
Keep the explicit End/Home path available and check microphone restoration afterward. See
[native Jitsi calls](jitsi-calls.md) for the separate call handoff and acceptance
requirements. Launching a room is not proof of a connected two-party call.

## OTT-play FOSS on Capacitor

The requested Android client is the Capacitor application from
[`open-ott-play/ottplay-foss`](https://github.com/open-ott-play/ottplay-foss),
package **`play.ott.foss`**, launcher `play.ott.foss/.MainActivity`.
Set `app_ids.ottplay_native` to this package. The existing `ottplay_native` mode
name is retained for service compatibility; it does not select the separate
Media3 preview. The dashboard labels this action **OTTPlay FOSS**.

The compatible local Full build uses the last Capacitor Android source before
its packaging was removed:
[`f8634903aa051592ccf15f675b8d8df3212fe502`](https://github.com/open-ott-play/ottplay-foss/commit/f8634903aa051592ccf15f675b8d8df3212fe502).
The current local build identifies as **OTT-play FOSS Full 1.1.42-show5.2**, version code `10144`, minimum
API 24 and target API 36. Its Full manifest explicitly permits HTTP LAN sources.
The local HTTP command listener remains disabled. HA launches the fixed
application package through ADB. This Show build adds the existing
outbound command-server connection; see [CLI control](ott-command-server.md)
for registration, private credentials and supported operations.

The current local APK is 9,692,036 bytes; SHA-256
`2d48d416ac086dbe5cc893d29ef95e257ec17848fde1b002cee8bb6e2e865b71`.
Its signing-certificate SHA-256 is
`811c6a2e06e574d3906279229196eabb61e4424662087e98e0d1683693dd0d55`.
These identify the local artifact, not an official publisher release. Another
build may have different archive bytes; preserve the local signing identity for
in-place upgrades. The release manifest is non-debuggable and the APK has no
ABI-specific `.so` libraries. The signed Full distribution audit passed.

The local [startup patch](../patches/ottplay-foss-capacitor-startup.patch) removes
the remaining splash icon from `startPlayer()` and supplies explicit transparent
posters for the main and picture-in-picture video elements. Without a poster,
Android WebView supplies its own gray play-circle bitmap; removing app artwork
alone does not remove that fallback. Native Cast controls are also suppressed.
Buffering/error messages and the player's aspect-ratio sizing remain intact.
Initial playback uses the backend's existing readiness path, without a new
handler that would override a deliberate pause. The patch updates the local
version and includes startup, poster and readiness/pause regression checks.

Apply the [remote-control patch](../patches/ottplay-foss-capacitor-remote-control.patch)
second. It ports the acknowledged command/RPC transport from upstream
`a18cd4c5c9982ef5c8776c9fb7cc2076ba7de05e` and adds a limited adapter for this
historical player. Its SHA-256 is
`d2d7bccb9be09dfa6293f0c42656742342e0bfee447410b1587b8bf8a4cf6a07`.
It uses the existing native HTTP bridge, keeps the local listener disabled, and
excludes connection credentials and consent from exported settings. See
[the supported commands and connection lifetime](ott-command-server.md).

This is a historical source build, not a new upstream release. The current
upstream branch has archived the Android bridge and removed its Gradle packaging
workflow; see the
[archived Android build notice](https://github.com/open-ott-play/ottplay-foss/blob/8fd0762/android/README.md).
Apart from the documented command-server backport, the Full build does not
include subsequent web/iOS changes. Do not run
`cap sync android` in the current shared checkout to recreate the old application.
A future refreshed Capacitor APK needs an explicitly restored and tested build.

The older [published 1.1.41 APK](https://github.com/open-ott-play/ottplay-foss/releases/tag/v1.1.41)
was verified and could launch on the Show, but its local-catalogue playback check
produced no channels. That APK lacks the Full manifest's explicit cleartext
permission. App launch alone is not playback acceptance. The pilot therefore
uses the Full source build for the local HTTP installation.

### Reproduce the local build and installation

Use Node 22 or newer, JDK 21, Android SDK platform 36, Android SDK Build Tools
36.0.0, `adb` and an existing checkout of `open-ott-play/ottplay-foss` containing
the pinned commit. Set `JAVA_HOME` and `ANDROID_HOME` for that toolchain. The
source supplies its Gradle wrapper and locked npm dependencies.

Run from the local conversion checkout. Its `private/` and `downloads/`
directories are ignored. Extract into a **new empty** directory; do not overlay
another checkout or a previous build:

```bash
mkdir -p private/ottplay-capacitor-build-f863490 downloads
# This checkout must contain the pinned historical commit.
git -C /path/to/ottplay-foss archive f8634903aa051592ccf15f675b8d8df3212fe502 | \
  tar -x -C private/ottplay-capacitor-build-f863490
(
  cd private/ottplay-capacitor-build-f863490
  patch -p1 < ../../patches/ottplay-foss-capacitor-startup.patch
  patch -p1 < ../../patches/ottplay-foss-capacitor-remote-control.patch
  npm ci
  node tests/test_show5_startup.cjs
  node tests/test_show5_remote.cjs
  node tests/test_command_server.cjs
  node tests/test_port_engine_lifecycle.cjs
  npm run android:full:release
)
cp private/ottplay-capacitor-build-f863490/android/app/build/outputs/apk/full/release/app-full-release-unsigned.apk \
  downloads/ottplay-foss-capacitor-full-1.1.42-unsigned.apk
```

The upstream build command audits the generated Full distribution and APK.
Leave `KEYSTORE_FILE` unset for this unsigned-build procedure. Sign it with a
persistent local key before installation. Use SDK Build Tools' `zipalign` and
`apksigner` on `PATH`:

```bash
mkdir -p private/ottplay-capacitor-signing
chmod 700 private/ottplay-capacitor-signing
# First installation only. Reuse an existing key for later upgrades.
# keytool prompts for the password; keep it out of shell history.
keytool -genkeypair -keystore private/ottplay-capacitor-signing/show5-ottplay.p12 \
  -storetype PKCS12 -alias show5-ottplay -keyalg RSA -keysize 3072 \
  -validity 10000 -dname 'CN=Show5 OTTPlay Local Sideload'
chmod 600 private/ottplay-capacitor-signing/show5-ottplay.p12
zipalign -f -p 4 downloads/ottplay-foss-capacitor-full-1.1.42-unsigned.apk \
  downloads/ottplay-foss-capacitor-full-1.1.42-aligned.apk
apksigner sign --ks private/ottplay-capacitor-signing/show5-ottplay.p12 \
  --ks-key-alias show5-ottplay \
  --out downloads/ottplay-foss-capacitor-full-1.1.42-local.apk \
  downloads/ottplay-foss-capacitor-full-1.1.42-aligned.apk
apksigner verify --verbose --print-certs downloads/ottplay-foss-capacitor-full-1.1.42-local.apk
# After checking the target's full serial and codename:
adb -s DEVICE_TRANSPORT install --no-streaming -r \
  downloads/ottplay-foss-capacitor-full-1.1.42-local.apk
```

Back up the key and password privately: another signing key cannot update an
existing installation in place. The pilot uses a persistent local key, not the
upstream publisher's identity. Installing through authorized ADB does not
require enabling a browser's “install unknown apps” permission.

Launch through HA with `mode: ottplay_native`, select **English** on first use,
and configure the authorized provider or playlist inside this app. It has its
own storage; settings are not inherited from the TV, browser or Media3 preview.
Set **Type of player for streaming** to **HLS.js** for this Show's LAN HLS source.
Automatic detection chose the browser player, which returned
`DEMUXER_ERROR_COULD_NOT_PARSE`. The existing provider-scoped `sPlayers=1`
preference persists the HLS.js choice without changing other installations.
For hls-proxy use its explicit `/playlist.m3u8` export rather than relying on
user-agent-dependent root-page behavior; see the
[hls-proxy documentation](https://www.hls-proxy.com/docs.php). Retain the existing
LAN listener and its returned stream URLs.

Home/Stop ends the owned app session and restores the clock. The unrelated
`play.ott.foss.nativeapp.preview` may remain installed, but is not this action's
target. No user data is deleted to make the switch.

### Separate web route and other players

`mode: ottplay` opens the existing OTT-play FOSS web/server UI in its own Android
browser. It uses a private configured player origin and separate browser storage.
The [public web demo](https://player.ottplay.here.now/) is a static HTTPS site,
not a proxy that makes an HTTP-only LAN source playable.

Do not navigate the OTT page inside VACA's authenticated WebView: the reviewed
native external-auth bridge does not restrict requesting-page origin. Keep
VACA's clock home intact and use the separately identified application/browser.
The clock page's camera/event activity pauses while hidden; verify its return
and the separate VACA voice service afterward.

The OTT-play Control Server controls a player that has already opted in and
connected. It is not an Android app launcher. Command acknowledgement is also
distinct from confirmed playback.

The optional `ottplayer` action refers to the unrelated `es.ottplayer.tv` product.
It is not required for our Capacitor client. Keep it hidden or disabled when
that package is not installed. Its website's APK download failure does not block
installing or launching `play.ott.foss`.

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
- Our Capacitor OTT-play FOSS Full 1.1.42-show5.1 opened through the HA action with
  `play.ott.foss/.MainActivity` in the foreground. The local M3U catalogue loaded,
  and the provider's HLS.js preference survived Home/Stop and relaunch. A known
  HD channel decoded 200 more frames over eight seconds during playback and
  125 frames during an eight-second cold-launch check, with no playback error.
  The main/PiP transparent poster and disabled native Cast controls survived the
  relaunch; no play-circle placeholder appeared. The separate web route opened
  but retains its own provider configuration.

The live panel hides the unrelated branded OttPlayer action.
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

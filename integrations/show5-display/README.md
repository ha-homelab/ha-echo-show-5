# Clock and motion cameras for the small Show display

This standalone page replaces the full Home Assistant dashboard with a large
clock. A matching Front or Porch motion event shows that camera for 30 seconds;
another event renews the lease, and the latest camera wins. Expiry returns to the
clock. Video and images keep their original aspect ratio with `object-fit: contain`.

Prepared revision **`20261004-r5`** adds transient-connection recovery and durable
backup handling. It is source-only and has not been deployed or accepted on the
physical Show; the observed hardware acceptance below belongs to r4.

Revision **`20261004-r4`** adds actual camera video through Home Assistant's
WebRTC API. The example configuration selects `cameraMode: "webrtc"`.
The peer receives only video, playback is muted, and the page never requests
a microphone or camera permission. There is no external font, UI framework,
HLS library or media session while the clock is showing.

Each video attempt has a 15-second startup deadline, including authentication.
The loading overlay clears only after playback starts and a decoded or presented
frame is confirmed; an ICE connection or `ontrack` event alone is insufficient.
A failed attempt is retried after five seconds while the motion lease remains
active. Ten seconds without decoded/presented-frame progress closes the session
and shows the camera as unavailable. The display can then retry within that same
lease. A video's advancing playback clock does not override this stall check.

Repeated motion renews the existing 30-second lease without restarting healthy
video. Hiding the page, expiry or switching cameras closes the peer, stops its
tracks and unsubscribes the HA offer session. Returning to the page shows the
clock; it does not replay earlier motion. A transient MQTT transport outage keeps
the current camera lease without extending it: video has its own authenticated
connection, and the existing 30-second expiry still applies. Authorization or
protocol failures and rejected subscriptions return to the clock.

## Configuration and authentication

Copy `config.example.js` to ignored `config.js`. Set the local time zone, the two
camera entity IDs and the exact MQTT motion topics already supplied by your
automation. Each role accepts either an exact string `payload`, or a JSON
`name` match configured with `jsonName`. Retained messages are ignored, so an old
motion event does not show a camera after reconnecting.

Use `cameraMode: "webrtc"` for live video. Each configured camera must advertise
HA WebRTC support and provide a stream the Show can decode. Set
`cameraMode: "snapshots"` explicitly to use the still-image fallback described
below. For compatibility with earlier configuration files, an omitted mode also
uses snapshots. There is no silent switch from failed video to still images.

Only `front` and `porch` camera roles are accepted. Do not use MQTT wildcards or
put camera URLs, passwords, access tokens or a refresh token in configuration.
HA serves `/local` files without authentication: the entity/topic mapping is
visible there even though obtaining camera images still requires authorization.
Keep the filled mapping out of the public Git repository.

The page uses VACA's existing native external-auth bridge. Short-lived tokens
stay in memory and authorize same-origin HA camera and WebSocket requests.
If HA rejects a video authentication challenge, the adapter forces one native
token refresh and retries once. Permission and transport failures do not trigger
a refresh loop. This does not create another HA account or add credentials to
static files.
The page needs an already authenticated VACA session. It deliberately contains
no browser login form and should be hosted on the **same HTTPS origin as VACA's
configured HA server**. Do not host it on a third-party site.

The installed HA `mqtt/subscribe` WebSocket command requires an administrator
session. Confirm that the existing session can subscribe; do not silently grant
an ordinary display account administrator access. If it cannot, the clock still
works but automatic camera activation needs a separately designed restricted
event adapter. Subscription failures are visible in `Show5Auth.status()`.

The video adapter opens its own authenticated same-origin HA WebSocket, obtains
the camera's client configuration, then exchanges offer, answer and bounded ICE
candidates. It uses only the bounded STUN/TURN configuration supplied by HA.
Media follows the negotiated ICE route, which must also be reachable from the
Show; working HTTPS signaling alone does not prove the media path works. Do not
expose a go2rtc management API to the browser or put its credentials in this page.

All scripts and styles are local, with a restrictive Content Security Policy.
The reviewed VACA native bridge does not itself enforce requesting-page origin;
do not add external scripts, frames or navigation to this authenticated page.

## Installation

1. Back up any existing `/config/www/show5-display` directory outside `/config/www`.
2. Copy the five assets `display.css`, `display.js`, `stream.js`, `auth.js` and the filled `config.js` to
   `/config/www/show5-display/`. Copy the source `index.html` as
   **`index-20261004-r5.html`**, with all five asset URL versions set to
   **`?v=20261004-r5`**. Do not copy tests or backup files.
3. Open `/local/show5-display/index-20261004-r5.html?external_auth=1` in the selected VACA
   WebView. Verify the clock and the sanitized `Show5Auth.status()` result.
4. Configure the selected device's persistent home path as described below.
   A one-time browser navigation alone does not survive VACA Refresh/restart.
5. Check each camera, the return to clock and the unchanged voice assistant.

HA `/local` responses can be cached for 31 days. VACA uses `LOAD_DEFAULT` and
its Refresh action does not clear the WebView cache. **Every deployed update,
including a configuration-only change, needs a new entry filename and a new
version on all five asset URLs in the HTML.** Change the selected entry's home
path to that new filename after copying the complete release. Keep a private
backup of the previous complete release; a rollback also needs a fresh release
ID because the original asset URLs may already be cached. Restarting the app
alone is not a cache invalidation strategy.

### Persistent VACA home path

The unmodified VACA integration uses a View Assist home mapping when one exists.
Without View Assist, its `ha_url` option alone cannot set a dashboard path:
Android replaces the URL path and uses the base server for token refresh.
**Do not append the clock path to `ha_url`.**

`vaca_dashboard_patch.py` adds an optional `ha_dashboard` path to the reviewed
integration's options flow. It is an explicitly maintained local patch, not an
upstream VACA feature. It checks exact source hashes and supports backup and
rollback; inspect its `--help` before use. Other devices retain the existing
View Assist/default behavior when the option is absent or blank.

Deploy the patch to the HA configuration volume, validate configuration and
perform one normal HA Core restart to load changed Python modules. An integration
reload alone does not reliably import edited Python code. Then edit only the
intended VACA config entry's options, retaining its existing `ha_url`, and set
`ha_dashboard` to `/local/show5-display/index-20261004-r5.html`. VACA adds `external_auth=1`.
The entry's existing update listener reloads that entry after saving options.

Check the selected device after VACA Refresh and an app restart. Recheck this
patch after every VACA/HACS update: an upgrade can replace the modified files,
and hash mismatch must be reviewed rather than bypassed.

For rollback, first clear the selected entry's dashboard override, then run
`python3 vaca_dashboard_patch.py /config/custom_components/vaca --restore-backup /config/YOUR_PRIVATE_BACKUP`
and restart HA Core. The helper refuses changed live or backup files. Restore the previous static directory if
needed. This workflow does not change wake-word files or voice pipelines.

## Validation

Run the offline tests from the repository root:

```bash
node --test integrations/show5-display/tests/*.cjs
python3 -m unittest discover -s integrations/show5-display/tests -p 'test_*.py' -v
```

On the selected device, inspect `Show5Auth.status()` without logging tokens.
Its MQTT-ready status establishes the event connection, not successful video
decoding. Use `Show5Display.showCamera('front', 30)` and then `'porch'` to test
video without publishing fake motion to shared household topics. Allow the
15-second startup budget; a five-second display lease can expire before video
starts. Check advancing decoded-frame counters or presented frames, then
`Show5Display.showClock()` and natural lease expiry. Confirm the video element's
`srcObject` is cleared and the HA offer subscription is released. Test a real
motion event separately. Confirm correct proportions and clock recovery after
reconnect. Never report synthetic event injection as a physical motion or
spoken wake-word acceptance test.

The clock remains local when HA is unavailable. Automatic camera events and
authenticated camera sessions require the HA connection. Native VACA voice remains
separate from this page; a functioning clock is not evidence that the microphone,
wake model, speech service or conversation pipeline works.

### Decoder compatibility and an optional Front relay

The tested Show could decode Porch's existing stream directly. Its native
decoder could not decode the original 2240-pixel-wide Front stream, although
that camera's JPEG snapshots displayed correctly. Resizing the HTML video
element cannot change the encoded resolution or codec profile received by the
decoder.

For an incompatible source, provision a separate **on-demand 480p H.264 Baseline
relay alias** on the media server and expose that alias as a HA camera. Point
only the display's `front.entityId` at this compatible camera, for example
`camera.front_display`, while keeping the Front motion rule. Preserve the
original camera stream for other consumers. The relay should transcode only
while it has a viewer; verify it stops when the display returns to the clock.
This is an optional server-side compatibility step, not a browser decoder or
an always-running background transcode. Confirm actual decoded video on the
Show before treating a new relay as accepted.

### Explicit snapshot fallback

With `cameraMode: "snapshots"`, the page requests an authenticated still image
one second after each successful response; the effective update rate also
depends on camera response time. This mode is not continuous video. The last
decoded image remains while its replacement downloads and decodes. A delayed
update badge appears after five seconds without replacement or a refresh
failure. After 15 seconds without replacement, the old image is removed.
Each request is bounded to ten seconds and 10 MiB, and requests never overlap.
Switching camera, hiding the page or lease expiry clears images and revokes
their object URLs. Select this fallback deliberately and deploy the changed
configuration under a new release version.

## Observed deployment, October 4, 2026

Revision `20261004-r4` was deployed to the second converted Show and selected as
its persistent VACA home path, preserving the other device options. On the real
WebView, Front's compatible rendition decoded at 854x480 and about 10 fps;
Porch's existing stream decoded at 1920x1080 and about 9 fps. Bounded 20-second
checks recorded increasing decoded frame counts and no JPEG proxy requests.
Native Android screenshots confirmed both camera views with preserved aspect ratio;
CDP screenshots can omit the hardware video surface and appear black.

A passive observation also captured a real Front MQTT activation without test
publications. Both display checks ended with the clock visible, an empty video `srcObject`
and all former tracks ended. The shared Front producer retained its identity
and original recording consumer. The separate display encoder stopped after
its final viewer disconnected; it is not preloaded. A bounded active sample
added no CPU throttling and stayed below 80 MiB; idle working memory returned
to about 7 MiB. These short checks are not a sustained capacity benchmark.

The companion infrastructure manifest is
[`025-go2rtc-show5.yaml`](https://github.com/4alvit/k3s-self-healing/blob/codex/show5-camera-stream/deployments/04-kerberos/025-go2rtc-show5.yaml).
It reads the existing relay, so the media route includes the HA/relay servers;
the distance between the physical camera and Show does not make it a direct
LAN camera connection. A single unsilenced 16 kHz mono VACA recorder remained
active after the video checks. These checks do not establish an unattended
Android restart or physical wake-word accuracy.

### Earlier snapshot acceptance

The second converted Show authenticated through the existing native session and
successfully subscribed to both configured motion topics. A real Front motion
event displayed a fresh 2240×1260 image without test MQTT publications. The Porch
camera returned 1920×1080 images during a direct display test. Device screenshots
confirmed a readable clock and aspect-preserving camera presentation. A bounded
five-second test returned to the clock, removed the image source and left zero
snapshot requests in flight. The normal configured lease is 30 seconds.
The versioned home path survived the selected device's HA Refresh action and
one VACA app restart. Native authentication, both subscriptions and an unsilenced
recorder returned automatically; an ensuing real Front event displayed an image.
This is an app restart check, not an Android power-cycle acceptance test.

The selected FCC voice pipeline was retained. Separately, a newer private wake
model was imported, selected and observed mapped in VACA's process, with one
unsilenced 16 kHz mono recorder. Physical spoken recognition remains an attended
acceptance test, not a consequence of the display checks.

HA stopped responding to local API requests during setup. One Core restart
restored API responses and loaded the reviewed dashboard-option patch. The busy
main-loop callback was not identified; these checks do not establish multi-day
HA or Wi-Fi reliability. Keep deployment receipts, device identifiers and camera
screenshots in ignored private storage.

### Camera flicker correction

The owner subsequently reported a repeating image/unavailable cycle. A device
trace reproduced it: successful camera downloads took 2.89–3.02 seconds, with a
further one-second polling delay. The original three-second image expiry
therefore hid healthy frames for roughly one second between updates. HTTP
requests succeeded and native authentication stayed connected.

Snapshot revision `20261004-r3` keeps the last good image for the bounded interval above,
decodes its replacement offscreen before swapping it, and preserves the image
through a transient fetch/decode failure. It does not enable HTTP caching of
camera responses. Regression tests reproduce three-second downloads, delayed
decode, transient failures and cancellation during a camera switch. The normal
30-second motion lease and voice configuration are unchanged.

After deployment, a 15.5-second device trace showed four image loads, a single
initial loading state and no unavailable/blank intervals between frames. Camera
responses still took 2.66–2.85 seconds: the improvement came from frame retention
and replacement, not from assuming that the camera had become faster.

# Clock and motion cameras for the small Show display

This standalone page replaces the full Home Assistant dashboard with a large
clock. A matching Front or Porch motion event shows that camera for 30 seconds;
another event renews the lease, and the latest camera wins. Expiry returns to the
clock. Images keep their original aspect ratio.

The camera view requests authenticated snapshots at approximately one per second
after each successful response. It is **not a full-frame-rate video stream**.
There is no camera audio, microphone capture, external font, UI framework or
continuous image request while the clock is showing. The last decoded image
stays visible while its replacement downloads and decodes, including across a
transient refresh failure. A small delayed-update badge appears after five
seconds without a replacement or a refresh failure. After 15 seconds without
a replacement, the old image is cleared and the camera is shown as unavailable.
Requests stop when the page is hidden or the lease expires; changing cameras
immediately clears the previous camera's image.

## Configuration and authentication

Copy `config.example.js` to ignored `config.js`. Set the local time zone, the two
camera entity IDs and the exact MQTT motion topics already supplied by your
automation. Each role accepts either an exact string `payload`, or a JSON
`name` match configured with `jsonName`. Retained messages are ignored, so an old
motion event does not show a camera after reconnecting.

Only `front` and `porch` camera roles are accepted. Do not use MQTT wildcards or
put camera URLs, passwords, access tokens or a refresh token in configuration.
HA serves `/local` files without authentication: the entity/topic mapping is
visible there even though obtaining camera images still requires authorization.
Keep the filled mapping out of the public Git repository.

The page uses VACA's existing native external-auth bridge. Short-lived tokens
stay in memory and authorize same-origin HA camera and WebSocket requests.
This does not create another HA account or add credentials to static files.
The page needs an already authenticated VACA session. It deliberately contains
no browser login form and should be hosted on the **same HTTPS origin as VACA's
configured HA server**. Do not host it on a third-party site.

The installed HA `mqtt/subscribe` WebSocket command requires an administrator
session. Confirm that the existing session can subscribe; do not silently grant
an ordinary display account administrator access. If it cannot, the clock still
works but automatic camera activation needs a separately designed restricted
event adapter. Subscription failures are visible in `Show5Auth.status()`.

All scripts and styles are local, with a restrictive Content Security Policy.
The reviewed VACA native bridge does not itself enforce requesting-page origin;
do not add external scripts, frames or navigation to this authenticated page.

## Installation

1. Back up any existing `/config/www/show5-display` directory outside `/config/www`.
2. Copy `display.css`, `display.js`, `auth.js` and the filled `config.js` to
   `/config/www/show5-display/`. Copy the source `index.html` as
   **`index-20261004-r3.html`**. Do not copy tests or backup files.
3. Open `/local/show5-display/index-20261004-r3.html?external_auth=1` in the selected VACA
   WebView. Verify the clock and the sanitized `Show5Auth.status()` result.
4. Configure the selected device's persistent home path as described below.
   A one-time browser navigation alone does not survive VACA Refresh/restart.
5. Check each camera, the return to clock and the unchanged voice assistant.

HA `/local` responses can be cached for 31 days. VACA uses `LOAD_DEFAULT` and
its Refresh action does not clear the WebView cache. **Every deployed update,
including a configuration-only change, needs a new entry filename and a new
version on all four asset URLs in the HTML.** Change the selected entry's home
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
`ha_dashboard` to `/local/show5-display/index-20261004-r3.html`. VACA adds `external_auth=1`.
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
Use `Show5Display.showCamera('front', 5)` and then `'porch'` to test images and
expiry without publishing fake motion to shared household topics. Test a real
motion event separately. Confirm camera cleanup, correct proportions and clock
recovery after reconnect. Never report synthetic event injection as a physical
motion or spoken wake-word acceptance test.

The clock remains local when HA is unavailable. Automatic camera events and
authenticated images require the HA connection. Native VACA voice remains
separate from this page; a functioning clock is not evidence that the microphone,
wake model, speech service or conversation pipeline works.

## Observed deployment, October 4, 2026

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

Revision `20261004-r3` keeps the last good image for the bounded interval above,
decodes its replacement offscreen before swapping it, and preserves the image
through a transient fetch/decode failure. It does not enable HTTP caching of
camera responses. Regression tests reproduce three-second downloads, delayed
decode, transient failures and cancellation during a camera switch. The normal
30-second motion lease and voice configuration are unchanged.

After deployment, a 15.5-second device trace showed four image loads, a single
initial loading state and no unavailable/blank intervals between frames. Camera
responses still took 2.66–2.85 seconds: the improvement came from frame retention
and replacement, not from assuming that the camera had become faster.

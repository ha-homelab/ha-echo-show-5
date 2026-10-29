# Room panel and offline clock

Display revision `20261029-r13` adds an optional room panel to the existing
960 × 480 clock. The clock remains the default view. **Room** opens six large
action buttons, up to four readings, and local timer controls. **Clock** closes
the panel. Camera playback still occupies the whole screen without room controls,
titles or a clock overlay. Camera startup is silent: the current clock/menu
remains visible until a decoded image or playable video frame is ready. Failed
preparation does not replace the interface with an error. Opening Room cancels
pending preparation, so a late frame cannot take the controls away. An already
playing camera ignores other-camera automatic motion events; manual camera
selection remains explicit.

The panel uses the existing native VACA authentication bridge. It reads only
configured HA entities and invokes only configured, no-argument room scripts.
It does not expose an arbitrary service, command, URL or Android-shell input.
Access tokens stay in memory. Room configuration is a public static file and
must never contain credentials.

## Configure the display

Copy the optional `room` section in
[config.example.js](../integrations/show5-display/config.example.js) into the
deployment's ignored configuration. Enable `remoteTarget` with the same prefix
used by the generated room package.

- `actions`: at most six `{id, label, script}` records. The script must be
  exactly `script.<remoteTarget>_room_<id>`. Labels are at most 32 characters.
  The browser sends an empty JSON body. The HA package supplies fixed target
  entities, preset media and session policy.
- `status`: at most four `{entityId, label}` records. An optional `attribute`
  selects `temperature`, `current_temperature`, `humidity` or `wind_speed`.
  This supports climate setpoints and weather temperature even if the weather
  provider's overall state is unknown. Entity domains are restricted to
  sensor, binary sensor, climate, weather, input number and input boolean.
- `timerEntity`: a HA timer to show beside the clock. The display uses its
  absolute `finishes_at`; it does not restart a timer on reconnect.
- `reminderEntity`: a sensor with a `message` attribute and future `expires_at`
  (ISO timestamp or Unix seconds). `idle`, `off`, `none`, `unknown` and
  `unavailable` states remain hidden. Messages expire locally even offline.
- `dismissScript`: exactly `script.<remoteTarget>_room_dismiss`. **Dismiss**
  calls this script and waits for the next state refresh.
- `sessionEntity`: the generated room session sensor. When configured, a local
  timer chimes only if its recently received state is `idle` and `busy` is
  explicitly false. Calls, media, unknown state and stale ownership suppress
  sound; the overdue visual reminder remains. Automatic motion-camera playback
  also checks this sensor immediately before starting, with one concurrent
  check and a five-second minimum interval. An open room menu suppresses motion.
  Slow or failed ownership checks discard that event instead of replaying it.
- `staleSeconds`: 30–3600 seconds; default 120. Readings are fetched sequentially
  every 30 seconds while the page is visible. A failed refresh retains the last
  value and its original receipt time. A `~` prefix marks stale or unavailable
  data. Zero remains a real value, not an availability fallback.

Freshness here means **time since a successful HA read**, not proof that the
physical sensor produced a new measurement. The original `last_updated` is
retained by the model. A steady sensor may legitimately have an old change
timestamp; use an integration-specific freshness entity where available.

Action buttons report completion only after the HA service request succeeds.
State reads have a ten-second deadline; fixed actions have ninety seconds to
allow the existing Android and SIP checks to finish. An unconfirmed outcome is
shown and is never automatically retried, because the first
request may have changed state before its response was lost.

## Local timer behavior

**5 min**, **15 min** and **30 min** start a local timer. Its only persistent
data is a version, start timestamp and deadline. **Clear** removes that journal.
Reloading the page restores a valid timer; an overdue timer from the previous
24 hours shows **Time is up**. Corrupt, implausibly future, oversized-duration
and older journals are ignored.

Tapping a timer attempts to unlock browser audio. Expiry can play three soft
tones using Web Audio while the page is visible and the room session is idle.
This is **not an Android alarm service**: a closed or suspended WebView, an app
restart, a device reboot, blocked autoplay or a changed system clock can prevent
an on-time sound. After a reload without another gesture, the visual reminder
works but audio may remain blocked. Use the generated HA timer/reminder path for
server-managed reminders; neither path is an emergency alarm.
If the session sensor is configured and HA is offline, its eventual stale state
suppresses sound too; the local visual deadline still works.

## Offline page and photo frame

`offline: true` enables a service worker only in a secure browser context that
supports it. It caches the page, its eight static dependencies and the public
configuration under the exact display directory. Installation must finish
online before an offline reload can work. Files from another display directory
have a different scope and cache. The worker never intercepts HA API calls,
camera streams, bearer-authenticated requests or external origins.
Each installation stages a complete cache generation before publishing its
pointer. An interrupted upgrade preserves the previous complete offline shell.

The first navigation normally starts from the network. Subsequent offline
navigation can render the cached clock, room UI and local timer journal. HA
actions remain unavailable; live readings are not persisted across reloads.
An already open page retains old readings in memory with freshness labels.
This is a browser fallback, not proof that every VACA/Android WebView can start
its native host while HA is unavailable. Test that exact device separately.

`photos` optionally selects up to twelve static `photos/<name>.jpg`, `.jpeg`,
`.png` or `.webp` paths in the same display directory. Files rotate every thirty
seconds behind the clock with low opacity so time stays readable. Each cached
image is limited to 2 MiB. Removing an image from the configured list removes
its cached copy on the next update. External URLs, query strings, path traversal
and SVG are rejected. **HA `/local` is publicly readable to anyone who can reach
the server; do not place private photographs there.** No album is enabled by
default.

To disable the fallback, set `offline: false` for future registration and remove
the existing service-worker registration/cache through the browser's site
settings. Clearing the site's storage also removes local timer journals. A new
versioned display directory naturally receives a new independent scope.

## Validation

The display test suite covers exact action bindings, state allowlists, bounded
response bodies, no retry after ambiguous command failure, attribute readings,
fresh/stale/zero values, timer deadline reconciliation and offline cache scope.
All four interface catalogs (English default, German, Spanish and opt-in Russian)
have matching keys. Native device deployment and acoustic results belong in the
private rollout receipt; source tests do not establish hardware acceptance.

Run:

```sh
node --test integrations/show5-display/tests/*.cjs
```

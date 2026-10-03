# A compact Home Assistant panel for the Show

This guide provides a **portable proposal** for the Show's 960×480 landscape display. [The dashboard template](../templates/home-assistant/dashboard.template.json) uses only native HA cards. Its screen/camera control scripts are operator-supplied bindings, and its call buttons are deliberately inactive until a call route exists. Rendering the template does not install integrations, create those scripts or change HA.

The existing device has demonstrated Companion login/dashboard rendering, camera retrieval through HA, video operation alongside the VACA service, manual camera restart and operator-confirmed double-tap screen wake. A separately configured home panel also rendered at 960×480 and remote wake worked. These results do **not** validate every view and binding in this portable template, physical custom voice activation, music output or real video calls. The intercom integration's [tested results](../integrations/show5-intercom/README.md#tested-results) distinguish bounded audio and synthetic signaling checks from physical acceptance.

## Layout

Use a dedicated dashboard with six short tabs and a **panel view containing one two-column grid** per tab. Each column holds a short stack; avoid long entity lists, nested browser frames and full-width video. The device's Android display density, HA header and text scaling affect the actual viewport, so confirm fit physically rather than promising a fixed number of visible pixels. [Native panel views](https://www.home-assistant.io/dashboards/panel/), [grid cards](https://www.home-assistant.io/dashboards/grid/).

- **Home:** voice connection, screen state and the selected music target on the left; an announcement text helper with **Announce**, **Assist** and **Main home** buttons on the right. Main home opens the household's existing dashboard; this panel needs no arbitrary room light, temperature or contact bindings.
- **Camera:** one half-width live picture with start/release controls and connection state beside it. The viewport is **16:9**, with **`fit_mode: contain`**. The 640×480 source stays proportional and fully visible with unused space; neither cropping nor stretching is required. [Picture-entity sizing](https://www.home-assistant.io/dashboards/picture-entity/).
- **Screen:** brightness and awake state, separate wake/sleep commands, and a command to return the actual Show to its dashboard. Navigating a dashboard on another phone does not itself navigate the Show.
- **Voice:** satellite state, software microphone mute and a native Assist button. Assist opens **without immediately listening**, preserving a deliberate microphone handoff while VACA is active.
- **Music:** the configured player's native media card, play/pause and stop. The target may be a tested Show player or another chosen room player; its name does not prove the Show is the physical output. [Media control card](https://www.home-assistant.io/dashboards/media-control/).
- **Calls:** an explicit unconfigured state. Add working call actions only after a backend, permissions and recovery procedure are tested; displaying a call icon does not create intercom.

Native cards require no custom frontend resources, card-mod, kiosk plugin or browser-mod. The optional VACA integration is a device/backend dependency, distinct from a custom dashboard card. Companion fullscreen remains an app setting; it does not remove all HA header elements or establish unattended kiosk behavior.

The six tabs already provide navigation: the camera controls omit a duplicate navigation row, and status cards omit decorative titles. Keep labels short and start with the compact Home tab. A software keyboard temporarily covers much of this screen; finish editing the announcement and dismiss it before tapping Announce. If the actual density leaves insufficient height, remove explanatory cards or a status row before shrinking touch targets. No screenshot or physical fit test of this proposal has been completed.

## Render a private copy

The template is JSON, which is also accepted as a YAML mapping in HA's raw dashboard editor. It has no device addresses, credentials, model IDs, household entities or camera images. Keep the filled mapping and rendered dashboard under ignored `private/`.

```bash
mkdir -p private
cp templates/home-assistant/mapping.example.json private/show-dashboard-map.json
```

Replace every `replace_me` value with an existing entity or a tested wrapper script in your own installation. `DASHBOARD_PATH` is the dedicated dashboard's local path, such as `/show-panel`. `MAIN_HOME_PATH` is the existing household dashboard/view, for example `/lovelace/0` or `/dashboard-home/main`; it is a local route, never an external URL or an address containing credentials. The six view paths are `home`, `camera`, `screen`, `voice`, `music` and `calls`.

```bash
python3 scripts/render_dashboard.py \
  --mapping private/show-dashboard-map.json \
  --output private/show-dashboard.json
```

The renderer checks required mapping keys, entity syntax/domain, a local dashboard path and unresolved placeholders. It writes a **new mode-0600 file inside this project's `private/` only** and refuses to overwrite an existing file. It never contacts HA or any device. These checks establish a well-formed local binding, not successful device operation.

If an existing private HA state export is available, add **`--states private/entity-states.json`**. It must be a JSON array of HA state objects containing `entity_id`. This additionally refuses mappings absent from that snapshot. It does not prove the states are current, that entities are available, that a player supports every action or that a script has been tested.

Create a separate manual HA dashboard at the configured path, save a private copy of its existing configuration, then paste the rendered JSON into that dashboard's raw configuration editor. Do not replace the global default dashboard merely to add this display. Choose the dedicated panel for the Show's Companion user/device, open each tab, and verify a harmless action before enabling broader controls. Keep maps, rendered config, state exports and screenshots private.

## Binding contracts

The example entity names are **placeholders, not promised VACA entities**. Find the entities actually created by the installed integrations and adapt the template if their domains differ. Remove a card rather than inventing a successful state for an unsupported feature.

- `ANNOUNCEMENT_TEXT`: a dedicated existing `input_text` helper. Editing it only changes helper state; the **Announce** button explicitly starts the mapped script. Keep announcement text out of public examples and remember that helper values may be retained in HA history.
- `CAMERA`: the core MJPEG camera from [the camera guide](camera-and-intercom.md). Prefer an MJPEG URL without a separate still-image URL; do not place camera Basic credentials in the card.
- `VOICE_SATELLITE`, `VOICE_MUTE`: the installed VACA satellite and its software mute entity. The mute switch does not report the hardware privacy switch, and an idle satellite is not proof of usable acoustic input.
- `SCREEN_BRIGHTNESS`, `SCREEN_AWAKE`: real display controls/telemetry if supported. The example expects a `number` and `binary_sensor`; inspect the actual domains before mapping. Display brightness is not camera exposure.
- `MUSIC_PLAYER`: the explicitly chosen `media_player`, with its real supported play/pause/stop capabilities. Confirm sound on the intended output and reachability of generated media URLs before calling music playback verified.

The six script bindings keep device-specific operations out of the public layout:

1. **`SCREEN_WAKE_SCRIPT`** wakes the display through a supported device command without toggling the physical privacy switch. **`SCREEN_SLEEP_SCRIPT`** similarly sleeps the screen without changing microphone privacy. Read back both states where telemetry exists.
2. **`RETURN_HOME_SCRIPT`** navigates the intended Show's Companion instance to the configured dashboard. Native dashboard navigation changes only the client receiving the tap; this wrapper is for device-targeted return. Use a verified Companion notification/deep-link path or supported VACA control, with credentials kept in HA. [Companion command reference](https://companion.home-assistant.io/docs/notifications/notification-commands/).
3. **`CAMERA_START_SCRIPT`** deliberately launches the installed camera app, restores the chosen front camera/settings if needed, verifies authenticated video, and returns the display to Companion. It must not silently enable recording or microphone permission.
4. **`CAMERA_RELEASE_SCRIPT`** fully releases the camera app when privacy or another camera owner requires it. `/control/stop` only gates media delivery and can leave capture warm. The tested full-stop fallback is Android app force-stop followed by process/listener checks; implement it only through an already authorized, identity-checked device-control path.
5. **`ANNOUNCEMENT_SCRIPT`** reads the text helper when invoked, rejects blank/unavailable values, and sends a short announcement to the intended device through an already tested HA route. Keep the destination and provider configuration in HA; avoid shell interpolation and do not infer successful sound from an accepted service call. A small maximum text length and single-run mode are useful operator choices.

The renderer does not create these wrappers. The [portable HA package](../examples/home-assistant/README.md) supplies example screen wake/sleep, return-home and announcement scripts that can be mapped after replacing its generic entities. For example, map `ANNOUNCEMENT_TEXT` to its message helper and `ANNOUNCEMENT_SCRIPT` to the helper-reading `echo_show_say_message` script, not the separate script that requires a message argument. Camera start/release wrappers still require a reviewed device lifecycle implementation or removal of those buttons. Do not use generic unscoped ADB commands or select the first connected USB device. Normal dashboard use should not require an unattended root shell or publicly exposed device-control port.

## Voice, music and calls must share resources deliberately

Keep one continuous wake-word listener: VACA owns that role in the current extension and official Companion wake detection stays off. The native **Assist** action uses the last-selected pipeline and starts with `start_listening: false`; select the intended language in the dialog without changing the global HA default. To use Companion's microphone button, first settle and verify its microphone handoff from VACA. [Native Assist actions](https://www.home-assistant.io/dashboards/actions/).

Use independent screen controls and physical double tap for display wake. The Show's Mute/Power coupling can change privacy and screen state together; a running recorder or `silenced:false` does not rule out hardware mute. Physical double tap and the remote wake route have been checked. Remote sleep also passed at the Android display-state level after disabling the ROM's default Always-on Display: KEY223 produced Display Power OFF while wakefulness remained Dozing; KEY224 restored Awake and Display Power ON. Test the template's actual bindings independently and require actual display OFF, rather than an HA switch state or the word Asleep. See [the minimal setting change and rollback](android-and-home-assistant.md#screen-sleep-and-always-on-display).

Music does not establish acoustic echo cancellation. Verify volume control, actual sound, interruption by a deliberate voice command and restoration afterward. Avoid using a paused music entity as a proxy for microphone release or interpreting a successful `play_media` action as proof of audible output.

Intercom and video calls require a separate call implementation. The camera application's audio endpoints provide an experimental half-duplex route; native Linphone or SIPCore with a PBX are different call routes described in [the intercom guide](camera-and-intercom.md#experimental-audio-and-microphone-handoff). Before a call, verify microphone handoff from VACA; before a **video** call, also release the front camera from Android IP Camera. On completion or failure, restore camera streaming, Companion foreground and VACA listening. A transport connection does not prove ringing, intelligible two-way sound, remote video or hang-up recovery.

## Acceptance for this panel

After deployment, verify all six tabs at the actual display density; camera proportions and touch targets; live device state and the main-home link; a short deliberate announcement on the intended output; screen wake/sleep without privacy changes; brightness readback; return-to-dashboard targeting; supported player controls and audible output; and voice operation after each ownership transition. Keep unavailable features visibly unconfigured. Record reboot and network-interruption results separately from manual app restart, and repeat the [longer acceptance checks](android-and-home-assistant.md#acceptance-checklist) after adding another background app.

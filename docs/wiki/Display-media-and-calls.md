# Display, media and calls

[Wiki home](Home.md) · [Architecture](Architecture.md) · [Remote endpoint runbook](../remote-endpoint.md)

The five-inch screen works best with a clock while idle and full-screen content when needed. Administration remains in HA's separate phone/desktop panel. The small display does not need to render the entire HA dashboard.

## Clock and camera view

The [clock integration](../../integrations/show5-display/README.md) shows a large clock and listens for configured Front/Porch motion events. The normal motion lease is **30 seconds**; repeated motion renews the same healthy session rather than restarting it. The latest matching camera wins. At expiry the peer is closed and the clock returns. Retained MQTT messages do not replay old motion.

Camera video fills the screen without a title, clock header or playback controls. `object-fit: cover` preserves proportions and crops edges. It does not correct a distorted source or remove timestamps already embedded by the camera. The explicit black poster and decoded/presented-frame gate prevent Android's fallback play-circle from appearing before usable video.

WebRTC startup has a bounded deadline and stalled decoding is detected separately from signaling. The explicit snapshot mode is a fallback chosen in configuration, not a silent replacement for a failed stream. It keeps the previous decoded image briefly while fetching a replacement to avoid flickering between a valid frame and an error. See the [integration guide](../../integrations/show5-display/README.md) for exact timeout and cleanup rules.

A high-resolution stream may exceed the Show's decoder capabilities. An optional on-demand 480p H.264 Baseline rendition can solve a codec/resolution mismatch; changing CSS dimensions cannot. Preserve the original camera stream for other consumers, and verify that the additional encoder stops after its last viewer disconnects.

## Brightness and neutral color

The recorded baseline uses **manual 80% brightness**, automatic brightness off and a long screen timeout. HA's displayed percentage is not necessarily the effective value when Android automatic brightness is enabled. Verify the Android readback and the actual idle-dimming behavior in another app.

The local VACA timeout patch exposes **2,147,483 seconds**, corresponding to `2,147,483,000` Android milliseconds. That is roughly 24.8 days, **not infinity**. Keep the screen-always-on setting as documented. Recheck the patch after a VACA/HACS upgrade instead of accepting unknown source hashes.

Warm color may come from Lineage's separate **LiveDisplay** night-temperature controller. The documented neutral baseline disables its automatic day/night mode and uses neutral RGB values; disabling ordinary Android Night Light alone may not change LiveDisplay. These settings do not guarantee identical physical panel calibration. Follow the [brightness and color guide](../android-and-home-assistant.md#fixed-display-brightness).

## Remote activities

Generate the target-specific HA package and dashboard from private mappings using the [remote endpoint guide](../remote-endpoint.md). The supported modes include Home/Stop, Front/Porch cameras, music, fixed TV presets, OTT and Jitsi. An acknowledged command proves acceptance by the controller, not visible video or audible sound.

- **Music** uses the configured VACA media entity. Check audible playback and stop separately from HA's `playing` state.
- **TV** launches a fixed verified stream preset in the configured player. Validate media segments and decoding, not only the playlist's HTTP status.
- **OTT-play FOSS** refers to the project's Capacitor Android client (`play.ott.foss`). Its settings and provider account are separate from a TV or web installation. The `ottplay_native` command name is retained for compatibility.
- **OTT web** opens the separately configured site in its own browser; do not put unrelated sites into VACA's authenticated WebView.
- **OttPlayer** is a separate optional product. Hide its action if its package is not installed. It is not required for OTT-play FOSS.

The app/media lease defaults to 30 minutes and is bounded to 120 minutes. Manual camera viewing has its own bounded lease and takes priority over motion. Home/Stop terminates the activity owned by this endpoint and restores its clock. If cleanup fails, recorded ownership and pending restoration must be retained until actual readback confirms recovery.

## Jitsi and intercom

Use the operator-controlled Jitsi installation and fixed room in the private mapping. By default, launching Jitsi stops at prejoin. With an explicitly configured `jitsi_auto_join: true`, launch enters the fixed room with media enabled. Label the remote action accordingly so joining a call has a clear effect.

HA hands the microphone to the call application and saves the previous voice mute state. End/Home must stop the call and restore that saved state. Keep the bounded lease as a recovery mechanism, while recognizing that expiry cannot stop an unreachable Android device by itself.

Check local preview, received remote video, outbound video at the other participant and audible audio as distinct tests. A room timer or self-view proves neither remote delivery nor usable two-way sound. The [Jitsi guide](../jitsi-calls.md) records a successful two-way native pilot; the later [shared-room history](../remote-endpoint.md) has narrower observations and must not be presented as the same test.

The [camera/intercom pilot](../camera-and-intercom.md) and [HA intercom integration](../../integrations/show5-intercom/README.md) are separate experimental paths. Do not combine their capture permissions and ownership with Jitsi without a new coexistence test. The native Jitsi route is documented independently; complete acoustic and long-duration acceptance still belongs to the deployment operator.

## Language and deployment

The display supports configured `en`, `ru`, `de` and `es` language families and a separate 12/24-hour choice. It defaults to English and 24-hour time. [Localization](Localization.md) lists translated surfaces and exclusions. Deploy a complete cache-versioned release, including `i18n.js`; changing `config.js` at an old cached URL is not a reliable update.

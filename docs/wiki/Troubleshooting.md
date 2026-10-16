# Troubleshooting

[Wiki home](Home.md) · [Validation](Validation.md) · [Recovery](Installation-and-recovery.md)

Start with the smallest failing layer. Record the selected device, package/version and a bounded time window privately. An ordinary restart may recover a symptom, but does not establish its cause. Keep raw application logs private: they can contain tokens, model identifiers, transcripts and household state.

## The Show will not power on or USB is absent

Use the normal AC adapter as well as a known micro-USB **data** cable. The NAS USB port does not replace the power supply. Inspect the physical USB inventory and verify the intended full serial before taking an action. FASTBOOT, recovery and normal Android expose different interfaces. A device in Android without an ADB interface may simply need USB debugging enabled and the host key approved on its screen. Do not trigger conversion to solve a cable or authorization problem.

## HA says it cannot connect

Confirm Wi-Fi connectivity, the correct address/reservation and the configured HA **origin** first. Preserve an authenticated ADB recovery path. Inspect server health and the intended VACA entry, then distinguish authentication failure from transport failure. A page can be cached while HA is unreachable.

HTTP **403** is a response from an HTTP service or intermediary; it is not itself proof of failed DNS or an invalid clock. Inspect the actual responding endpoint and authentication status. Incorrect time can break TLS validity checks, but avoid disabling certificate verification. Check the device clock and intended certificate rather than guessing from a generic browser message.

Use VACA's separate dashboard-path option for its home page; do not put that path into the base HA server URL. See [clock authentication](../../integrations/show5-display/README.md#configuration-and-authentication) and [stable network addresses](../stable-network-addresses.md).

When several displays fail together, check HA from an independent client before
changing their applications. A reverse proxy can return **502** while the local
clock continues to work from cached assets. In Kubernetes, an empty HA service
EndpointSlice and a `Pending` replacement pod point to a server-side outage.
Inspect scheduling events and node conditions: `DiskPressure` can evict HA and
prevent rescheduling even when the device's Wi-Fi and TLS connection are healthy.
After enough space is recovered, allow the kubelet's pressure-transition interval
to expire. Do not remove the protection taint, reset device data or delete HA
storage to hide the symptom. Recheck natural display reconnection and fresh video
after HA is ready; an old frame is not proof of recovery.

An HTTP **200** or a Kubernetes **Ready** condition only confirms the configured
health probe. HA can accept authenticated WebSockets before MQTT, Assist and
VACA have completed setup. Check the runtime state and the actual integration
entries, satellite entities and required commands. In this interval,
`mqtt/subscribe` can return `unknown_command`. Display **r11** retries that
specific availability failure with a capped backoff; older revisions can remain
in `subscription_forbidden` until the page reloads. Actual permission denials
still require correcting access, not a retry loop.

For storage incidents, distinguish unused rebuildable cache from application
data and recovery backups. Inspect the owning cache service's usage report and
use its supported prune API; do not remove containerd snapshots or HA data by
hand. Check free space again after the replacement image and integrations have
finished loading. Crossing the eviction threshold briefly does not establish
enough headroom for the next restart.

## Voice does not start or answer

Separate these cases:

1. **No activation:** verify the microphone is not hardware/software muted, the selected microWakeWord engine is running and the expected models actually loaded. Primary HA selection alone does not prove the secondary file was read. Check the threshold scale: HA `3.5` means model threshold `0.35`.
2. **Activation without recognized text:** check the selected pipeline's speech-recognition service, authentication, provider quota and connectivity. Local wake detection does not make cloud ASR available.
3. **Text recognized but no useful action:** inspect the chosen conversation agent and HA-exposed intents/entities. The original FCC text bridge does not automatically have arbitrary HA tools. Prefer supported native intents for common household actions.
4. **Answer generated but no sound:** fetch the TTS output, then test a short announcement on the target satellite. Service completion and physical audibility are separate. Check volume and a competing player/call before changing models.
5. **Unexpected activations:** record only bounded, sanitized detection evidence, test negative phrases and background audio, and reconsider threshold/model quality. Lowering the threshold again is not a general fix.

Only one continuous listener should own the intended capture path. End a stuck call through the endpoint's Home/Stop recovery path and verify the previous mute state is restored. Do not reset app data or reinstall before preserving private models and the existing satellite identity.

## Camera flashes, never starts or has a play icon

Inspect `Show5Auth.status()` without logging tokens. A ready event subscription does not prove video decoding. Test the same controller with a bounded manual camera action; do not publish fake motion to shared topics just to exercise the UI.

- **Old display or giant Play circle:** confirm the active entry URL and every asset use the same new release version. The release includes the explicit blank poster and frame-ready gate. Refresh alone does not invalidate all WebView caches.
- **Successful signaling but black video:** check advancing decoded/presented-frame counters. Confirm codec/profile/resolution compatibility and the actual negotiated ICE route. CSS cannot downscale the encoded stream for the decoder.
- **Video starts and repeatedly disappears:** distinguish decoder stalls from motion lease expiry. Repeated matching motion should renew a healthy session without restarting it. In snapshot mode, use the retained-frame implementation rather than shortening the expiration below normal download time.
- **Works remotely but not on the Show's network:** verify the media candidates are reachable from that network, not merely that the HTTPS page loads.
- **Clock never returns:** verify lease expiry, hidden-page cleanup, stopped tracks and released HA subscription. Do not leave an always-running compatibility encoder to conceal cleanup failure.

See the [display guide's exact timeouts](../../integrations/show5-display/README.md).

## Screen dims or looks yellow

Disable auto brightness, set the intended manual brightness and inspect the effective Android state. Check screensaver/always-on and the long timeout option, including whether an integration update overwrote its local patch. The maximum practical timeout is about 24.8 days, not infinite.

For warm colors, inspect Lineage **LiveDisplay** as well as Android Night Light. The devices can have different physical panel characteristics even after software filters match. Use the [documented display procedure](../android-and-home-assistant.md#fixed-display-brightness), and preserve user-selected brightness rather than installing an unexplained periodic reset.

## Jitsi shows only self-view or pauses video

Verify that the other participant is actually sending and that inbound video arrives at each endpoint. A preview is local capture, not a transmitted stream. Inspect ICE/DTLS, received packets, decoder frames and Jitsi bridge load/CPU throttling separately. The recorded shared-room incident included server scheduling pressure, so bandwidth adaptation alone did not prove a Wi-Fi problem.

Reduce capture resolution/frame rate or resolve server contention when measurements support it. A setting cannot force usable video through an unavailable transport. Keep Home/End available and check the voice listener after the call. See [Jitsi](../jitsi-calls.md) and [remote shared-room history](../remote-endpoint.md).

## OTT or music launches but does not play

Confirm the exact package and provider configuration. OTT-play FOSS, its browser route and the separate OttPlayer product do not share application storage. Check the playlist and media segments, protocol policy and selected decoder/player. A remote command acknowledgement or Android launcher activity is not playback evidence.

Keep credentials and command-server registrations in the private local store. Do not solve a network error by enabling unrelated browser installation permissions or by putting credentials into the public HA display configuration. The [OTT command guide](../ott-command-server.md) documents the outbound connection and supported commands.

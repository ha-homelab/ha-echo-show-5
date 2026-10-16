# Architecture and data paths

[Wiki home](Home.md) · [Voice](Voice-and-wake-words.md) · [Display and calls](Display-media-and-calls.md)

A converted Show runs Android 11, an authenticated HA client and the optional VACA wake-word listener. HA coordinates voice, camera events and remote actions. This is not one monolithic audio/video connection: each function has a separate transport and a separate acceptance test.

![System diagram showing the Show, Home Assistant, optional media services and the administration path.](../assets/architecture.svg)

## Device and administration

The **USB host** is a physical x86_64 Synology NAS used by the guarded conversion tools. Normal operation does not need a USB cable. Authorized network ADB can support maintenance on the tested ROM, but reachability after a power loss must be verified independently. Keep ADB authenticated and nonroot; network ADB is not a public service. See [Android and network ADB](../android-and-home-assistant.md) and [stable addresses](../stable-network-addresses.md).

Conversion tools bind one observed USB node into a nonroot, network-disabled container. The selected port and complete serial are checked at each stage. The NAS role in conversion does not imply that ordinary media traffic must traverse the NAS. Likewise, moving a service to another node does not prove that its media packets avoid an old proxy or relay.

## Voice processing

![Three selectable voice paths. Local Russian Home retains cloud recognition; FCC uses external speech and text providers; Homeway uses Homeway services.](../assets/voice-paths.svg)

Wake detection runs on the Show. VACA's two-model extension uses one microphone and feature extractor, a shared threshold and a shared cooldown. After activation, HA uses the selected satellite's Assist pipeline. **Two wake words do not select two backends:** either phrase activates the same chosen assistant.

The recorded Local Russian Home configuration uses FCC/NVIDIA recognition, local HA intents or local Ollama dialogue, then local Piper/Irina synthesis. Audio therefore still crosses a cloud boundary. The original FCC backup uses external recognition/synthesis and an external text model behind the privately hosted FCC gateway. A gateway running on your infrastructure does not make its upstream models local. Homeway remains a separate selectable route. Detailed provider, quota and capability limits are in [FCC backup](../fcc-voice-backup.md) and [cloud audio](../fcc-cloud-audio.md).

## Clock, motion and cameras

The lightweight clock runs in VACA's WebView from the same HTTPS origin as HA. VACA supplies short-lived authentication through its existing native bridge. The page consumes authenticated HA WebSocket events and opens a separate authenticated camera session only while needed. It does not request microphone or camera capture permission from the browser.

HA's `/local` static files are **not authenticated**. Filled entity/topic mappings are therefore public to anyone who can access that origin; tokens, passwords and recordings must never go there. The reviewed native bridge does not enforce the requesting page's origin. Keep the display's scripts/styles local, and launch unrelated websites in a separate browser/application.

Camera media follows the **negotiated WebRTC ICE route**, not necessarily the HTTPS signaling route. A compatible camera rendition may be supplied by a relay/transcoder. A camera five metres away is not proof of a direct connection. Confirm the selected candidate pair and server counters if avoiding cloud or WAN bandwidth matters. The diagram intentionally does not assert a specific physical network path.

## Calls and other media

Jitsi owns a separate camera/microphone session. HA coordinates start, end and restoration; the selected Jitsi installation carries conference signaling and media. Media can use a bridge, TURN or a direct path depending on deployment and negotiated connectivity. Confirm actual candidates and server placement before making bandwidth claims. Lower quality can help a constrained connection, but no setting guarantees video when the transport or server cannot deliver packets.

Music targets the configured VACA media entity. TV and OTT modes launch fixed, allowlisted applications or URLs through the identified Android endpoint. The OTT command server controls an already connected player; it is not a device installer or launcher. See [remote controls](../remote-endpoint.md) and [OTT transport](../ott-command-server.md).

## Failure boundaries

A working clock proves local rendering. It does not prove HA authentication, a camera stream, microphone capture or an available provider. An established WebSocket proves signaling; an increasing decoded-frame counter proves more about video delivery. A TTS URL proves less than downloaded audio, and downloaded audio proves less than an attended listening test. Use the [validation ladder](Validation.md) to report only what was actually checked.

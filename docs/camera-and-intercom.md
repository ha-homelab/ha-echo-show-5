# Optional camera and intercom pilot

This extension uses **Android IP Camera 0.14.0** by DigitallyRefined on the already converted Show 5 Gen2. The initial pilot is video only: camera access is granted while microphone access stays denied, so VACA can retain microphone ownership. Intercom is a separate experiment with explicit microphone handoff and half-duplex operation.

**Checkpoint, 2026-10-02:** the verified ARMv7 APK is installed on the Android 11 pilot device. Authenticated **TLS1.3** snapshot and MJPEG requests returned **200**, with valid JPEG images and visually confirmed camera output; unauthenticated access was denied. A **20.02-second** MJPEG sample contained **104 frames at 640×480**, averaging **5.19 fps**, with different first and last frames. The initial default-resolution snapshot was **1600×1200**. Camera boot start remains off.

Companion remained in the foreground while both camera and VACA foreground services ran. Camera and shared-storage read permissions are granted; camera microphone permission is denied, and VACA's **16 kHz mono capture remained active and unsilenced**. The previous display timeout was restored after diagnostics. HA's authenticated camera proxy returned a valid **640×480 JPEG**, and a dedicated camera dashboard was created with a standard live picture-entity card. Full process stop and manual restart passed, retaining authentication and camera settings. Camera boot start was confirmed off in the Android settings UI. Longer-term performance, audible playback, microphone/camera handoff during calls and camera reboot recovery are **not yet verified**. Source capabilities below are separate from these device acceptance results. This guide makes no firmware or boot-chain changes.

## Pinned APK and verification

Use package **`com.github.digitallyrefined.androidipcamera`** from the [official v0.14.0 release](https://github.com/DigitallyRefined/android-ip-camera/releases/tag/v0.14.0), selecting **`androidipcamera-0.14.0-armeabi-v7a-release.apk`** for this ARMv7 userspace:

- Size: **5,125,398 bytes**.
- SHA256: **`53388d91e475f2ab73390e2ad026d4eaa24d7e0918fd3ca143ff8c7f2ac13af6`**.
- Signing-certificate SHA256: **`1111be81c861e199c6485d367c37680c4b778fba301980d2f0f9a2800f77f70a`**.

[androidipcamera-artifact.json](../androidipcamera-artifact.json) records the official asset metadata, observed Android manifest and separate signature audit. The release digest matched the downloaded bytes; Android SDK `apksigner` verified the v2 signature with one signer, whose certificate matched the [pinned upstream README](https://github.com/DigitallyRefined/android-ip-camera/blob/4a723736d207f3a44bffb3d99417c9b30309f993/README.md). The APK requires SDK24 or newer and targets SDK34. This confirms artifact provenance and manifest compatibility, not camera HAL compatibility or reproducible compilation.

```bash
python3 scripts/artifacts.py fetch androidipcamera
python3 scripts/artifacts.py verify androidipcamera
```

The helper checks size, SHA256, APK suffix and archive CRC. It does not rerun `apksigner`, install an app, contact Android or configure HA. Downloads stay in ignored `downloads/`. Installation is an attended operation on the independently verified device; the existing `install-companion` command continues to install only the official Home Assistant app.

## Configure the video-only pilot

1. Open Android IP Camera on the verified device. On this Android 11 route, grant **Camera** and **Read external storage**. Deny **Microphone** and optional location access for the video pilot. Leave VACA's camera permission denied; permissions are per app.
2. Keep **Authentication enabled**. In the app's settings, configure **Authentication → Username / Password**. The reviewed app stores credentials in encrypted preferences; its password validation requires 8–128 characters with uppercase, lowercase and a number. Store the chosen values privately and enter them in HA's credential fields, not URL strings or public configuration examples.
3. Keep **TLS enabled** and **Start on Boot off** for the initial pilot. The defaults are HTTPS on TCP **4444**, a device-generated self-signed certificate and boot start disabled. The reviewed listener binds all interfaces; restrict access to the intended HA host and trusted clients on the private network. TLS initialization failure does not silently fall back to HTTP.
4. **Select the existing front camera explicitly.** The tested Show exposes camera **`0`**, while the app initially selected a nonexistent back camera. Inspect the authenticated **`/info.json`** camera inventory before choosing an ID on other hardware. For this Show, request a conservative initial video setting through authenticated GET **`/?camera=0&resolution=640x480&fps=8`**, or choose the equivalent camera and settings in the web panel. This requests a capture setting; verify the actual negotiated size and performance before treating it as a measured frame rate.
5. Verify a fresh snapshot and a sustained MJPEG stream before adding dashboard use. Keep test images, recordings, credentials, addresses and logs under ignored private storage.

Authentication is fail-closed while enabled: unset or invalid stored credentials produce **403** before endpoint routing; absent or wrong Basic credentials produce **401**, or **429** when the app's authentication rate limit applies. The bench's unauthenticated request received 429 while authorized image requests succeeded; this was denial, not an authentication bypass. Test denial and authorized access separately. Basic authentication depends on TLS to protect credentials in transit. The app's network, authentication and media behavior is documented in the [pinned server source](https://github.com/DigitallyRefined/android-ip-camera/blob/4a723736d207f3a44bffb3d99417c9b30309f993/app/src/main/kotlin/com/github/digitallyrefined/androidipcamera/helpers/StreamingServerHelper.kt).

An initial **no available camera** error on this front-only Show was resolved by selecting camera `0`; it did not establish a camera HAL failure. Check the inventory and selected camera before diagnosing the Android port. **Snapshot resolution is separate from stream resolution:** the app's default snapshot mode can return the sensor's full size even after requesting a smaller video stream. The observed 1600×1200 snapshot is separate from the measured 640×480 MJPEG frames; requested 8 fps yielded 5.19 fps in the short sample.

The pilot also set **`snapshot_res=stream`**, but that is **not a guaranteed stream-resolution snapshot**. The snapshot handler reuses a fresh MJPEG frame when available and falls back to a full still capture when there is no active viewer/fresh frame. That fallback may trigger physical capture, shutter behavior or camera rebinding. Use MJPEG-derived images in HA as described below instead of relying on this preference to make `/video/snapshot` lightweight.

## Add the camera to Home Assistant

Add the core **MJPEG IP Camera** integration from **Settings → Devices & services → Add integration**. The similarly named Android IP Webcam integration targets a different app/API and is not the route used here. The [official MJPEG guide](https://www.home-assistant.io/integrations/mjpeg/) describes the URL, credentials and per-camera certificate setting.

Use your device's actual address; `show-camera.example.com` below is a placeholder:

- **MJPEG URL:** `https://show-camera.example.com:4444/video/mjpeg`
- **Still image URL:** **omit it** for this pilot.
- **Username / Password:** the values configured in the camera app.
- **Verify SSL:** keep enabled with a certificate trusted by HA. For the pilot's self-signed certificate, disable verification **only on this camera integration** (`verify_ssl=false`). HTTPS still encrypts traffic, but this exception removes certificate identity verification; do not disable verification globally.

With `still_image_url` omitted, the reviewed core MJPEG implementation extracts the first JPEG from the stream for an image request. This avoids calling the app's physical still-capture endpoint for HA thumbnails. Keep `/video/snapshot` available for deliberate diagnostics, not as the preferred HA still image URL. See the [core MJPEG image implementation](https://github.com/home-assistant/core/blob/2026.9.1/homeassistant/components/mjpeg/camera.py), matching the tested HA version.

MJPEG supplies a video camera entity. It does not add the app's audio upload or a call button. Verify the camera entity can retrieve fresh images from HA itself, rather than assuming a browser on another network has the same access. No public port forwarding is part of this setup.

### Preserve the camera's proportions

The tested stream is **4:3**, while the Show display is **960×480 (2:1)**. Filling that entire screen can crop or stretch the picture. Compare a direct MJPEG frame with a full-resolution still before changing capture resolution to compensate for a display problem.

Use proportional fitting in the dedicated HA card. The 16:9 card viewport below fits this landscape screen with room for the HA header and card footer; the 4:3 image stays centered inside it:

```yaml
type: picture-entity
entity: camera.echo_show_camera # Replace with your camera entity.
camera_view: live
aspect_ratio: "16:9"
fit_mode: contain
show_state: false
```

The [picture-entity card's `contain` mode](https://www.home-assistant.io/dashboards/picture-entity/) preserves proportions and includes the whole image; unused space is expected on a wider display. `cover` crops and `fill` can distort the picture. Keep the view sized to fit the display height as well as its width. The camera app's own local preview is a separate renderer: this HA setting does not modify the APK. Use the HA camera view for the fitted display while the camera service runs in the background.

## Experimental audio and microphone handoff

The pinned source exposes two separate audio directions:

- **Show → browser/client:** authenticated **GET `/audio`** streams a WAV container containing **PCM16 mono at 44,100 Hz**. It requires the camera app's microphone permission. The request creates microphone capture when a subscriber connects and releases it on disconnection; use one audio subscriber for the pilot. `/audio/raw` requests unprocessed microphone input and is not an echo-cancellation solution.
- **Browser/client → Show:** authenticated **POST `/audio/upload`** accepts **raw PCM16 little-endian, mono, 44,100 Hz**, without a WAV header, for speaker playback. This direction uses Android `AudioTrack` and does not require the camera app to record the Show's microphone. The browser or sending client still needs permission for its own microphone if it captures live speech.

These endpoints are source-supported; successful HTTP transfer alone does not prove a person heard intelligible audio. They are not a ready full-duplex call system, and this project provides no echo canceller or automatic call orchestration. For the first intercom test, operate **half duplex**: listen, disconnect the Show audio subscription, then talk back. Keep one audio subscriber and avoid monitoring both ends in the same room.

Before deliberately testing Show microphone capture, **mute VACA and verify that it releases the microphone**, then grant the camera app `RECORD_AUDIO` and open the single intended `/audio` subscription. Official Companion's continuous wake-word listener stays off. After the test, close every camera audio subscription, verify capture has stopped, restore the camera app's microphone denial for video-only use, then unmute VACA and verify its engine and capture resume. Do not infer exclusive microphone ownership from an app's mute icon alone.

The app includes a web push-to-talk interface, but browser microphone access, certificate trust, audio routing and audible playback still need end-to-end testing. Native [Linphone for Android](https://www.linphone.org/en/download/) or [SIPCore with a SIP/PBX server](https://github.com/TECH7Fox/sipcore-hass-integration) are separate options for a later call workflow. SIPCore provides HA dashboard calling through WebRTC and requires its own SIP/PBX server and HTTPS HA access. No PBX, extensions or SIP calling have been configured or validated by this project. The camera APK itself does not establish a SIP, RTSP or ONVIF service.

Future **video calls also require front-camera ownership handoff**, separately from muting VACA to release the microphone. Stop Android IP Camera completely and verify its process/listener are gone before letting Linphone or a WebRTC client acquire the front camera. `/control/stop` can leave capture warm and does not prove camera release. End the call and verify the call client has released the camera before restarting the camera app, restoring the selected camera/stream settings and checking HA images and VACA capture. Do not assume the camera stream and a video call can continuously share the same front camera.

## Stop, recover and accept

**`/control/stop` stops media delivery, not the HTTPS listener.** Existing viewers disconnect and media endpoints return **503**, while the control routes remain reachable. Camera capture can remain warm; this control proves neither camera release nor service shutdown.

The app's **Exit App** path attempts service shutdown, but the reviewed lifecycle teardown can leave the listener running. Verify TCP4444 is closed. If it remains open, use Android **App info → Force stop**, then verify both listener closure and released capture resources. Do not relaunch the app during that closure check. Leave **Start on Boot off** until startup and teardown have been tested intentionally; upstream's boot receiver being present is not evidence of recovery on this ROM.

The bench's explicit Android force-stop removed the camera app process and made the TCP connection refuse. After waking the screen and manually opening the app, the authenticated MJPEG endpoint returned fresh JPEG data again. Camera `0`, 640×480, requested 8 fps and the snapshot preference survived the restart. Companion was then returned to the foreground. This manual app restart does not establish unattended recovery after a device reboot or end-to-end call handoff.

Before treating the pilot as usable, record privately:

1. Unauthenticated access denied, valid authenticated snapshot returned, and continuing MJPEG frames displayed in HA.
2. Actual frame dimensions, sustained rate, temperature/load and whether VACA capture continues during video-only operation.
3. Media-stop behavior, complete listener shutdown and successful manual restart without stale camera or microphone ownership.
4. For the optional intercom test, microphone handoff, intelligible audio in each direction, half-duplex operation and VACA recovery afterward.
5. Deliberate reboot/network-interruption behavior after any decision to enable camera boot start, followed by a longer coexistence test with the Companion dashboard and VACA.

Do not publish household images, audio, model names, transcripts, credentials or addresses as acceptance evidence. Keep the existing [voice acceptance checklist](android-and-home-assistant.md#acceptance-checklist) and [VACA operating constraints](vaca-private-wakeword.md) in scope when adding another background app.

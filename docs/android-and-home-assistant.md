# Android and Home Assistant after conversion

This guide starts **after** unlock, a verified off-device backup and successful LineageOS installation. It describes the intended setup and acceptance criteria; the current physical validation checkpoint is in [validation status](preparation-status.md).

## Scope

The target is **Echo Show 5 Gen2 / 2021 / cronos** running the unofficial **LineageOS 18.1 v0.4 / Android 11** build. The Show becomes an Android client of an existing Home Assistant server. Home Assistant Server does not run on the Show. Replacing Fire OS does not preserve Alexa, Amazon routines or Drop In.

Start with the official **Home Assistant Companion minimal APK** for a dashboard and Assist. VACA is an optional custom wake-word extension once the dashboard is working; record physical speech acceptance separately if it cannot yet be tested. TECHO5 is a separate Alpine Linux firmware path, outside this Android runbook.

## ROM capabilities and limitations

The pinned [LineageOS v0.4 release](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-cronos-v0.4) was published on 2026-09-05; its filename contains build date 20260904. The maintainer's Build 4 announcement reports camera photos/video, a fix for audio disappearing after several days, microphone improvements, lower minimum brightness and Bluetooth LE fixes. Older v0.3 camera reports should not be applied automatically to this build. [Build 4 announcement](https://xdaforums.com/posts/90726610/).

The ROM documentation still lists Wi-Fi fast-roaming problems and potentially quiet microphones. SELinux is permissive, deep sleep is disabled, the battery reading is artificial, and Mute also acts as the Android Power button. This is an unofficial Android 11 port with limited resources. [ROM maintainer's thread](https://xdaforums.com/t/rom-unofficial-11-cronos-lineageos-18-1-for-the-amazon-echo-show-5-2021.4772598/).

Booting with the red hardware Mute state engaged can leave the camera unavailable. When diagnosing that case, the maintainer recommends rebooting with Mute off and using double-tap-to-wake for the display. [Camera and mute explanation](https://xdaforums.com/posts/90728899/).

The Mute/Power coupling is two separate input paths: the privacy button sends **`KEY_POWER`**, while its hardware state sends **`SW_MUTE_DEVICE`**. Pressing it can therefore put the screen to sleep while unmuting the microphone, or wake the screen while muting it. On the tested device, Android reported `mLastSleepReason=power_button` and `mic mute FromSwitch=true`, confirming both paths. An active VACA recorder with `silenced:false` does **not** override or rule out this hardware microphone mute. [Build-era button mapping](https://github.com/amazon-oss/android_kernel_amazon_mt8163/blob/8d928c5176cc1ced93a564dd8a949a6cda3b8231/arch/arm64/boot/dts/mediatek/cronos.dtsi#L51).

For independent screen wake, enable **Settings → Display → Tap to wake**, then test a physical double tap with the red mute light off. The equivalent command inside an authorized, identity-verified Android shell is `settings put secure double_tap_to_wake 1`. Read back that setting and `mDoubleTapWakeEnabled`; these confirm configuration, not a successful physical touch-wake test. A selected-device `input keyevent 224` (Android `KEYCODE_WAKEUP`) is an independent USB recovery path that leaves the privacy switch unchanged. Keep hardware mute off for voice acceptance, and verify the hardware state separately from VACA's software mute switch. Do not remap keys or write arbitrary touch-driver sysfs files to work around this behavior.

Start with a small dashboard and one microphone-owning app. Far-field speech, interruption during music, reliable camera playback, DRM streaming and unattended operation require tests on the actual device. An Android boot alone establishes none of those capabilities.

## Complete initial Android setup and enable USB debugging

Finish the Lineage welcome/setup flow. If it offers **Update Lineage Recovery alongside the OS**, leave that option unchecked for this TWRP-based workflow. This is the project's recommendation to retain the existing TWRP recovery, not a stated requirement from the ROM maintainer.

Developer options are initially hidden. Open **Settings → About tablet** (or **About device**), tap **Build number seven times**, then open **System → Advanced → Developer options** and enable **USB debugging**. Connect the data cable and approve the intended NAS host's RSA key on the Show. Choose **Always allow from this computer** only when deliberately authorizing that project's persistent host key.

The scripts cannot approve this on-screen prompt for you. Once authorized, rerun USB inventory if its mode or node changed, then use the complete observed serial for `probe-android` and installation. USB enumeration without an ADB interface before debugging is enabled does not by itself indicate a failed Android boot.

## Pinned Companion APK

The selected artifact is **Home Assistant Companion 2026.8.4-minimal** from the [official release](https://github.com/home-assistant/android/releases/tag/2026.8.4):

- Downloaded filename: `home-assistant-2026.8.4-minimal.apk`; upstream asset: `app-minimal-release.apk`.
- Size: **51,871,377 bytes**.
- SHA256: `8f58a7df71c61447d3370f5d5956a66e3523625dc4b51c8434bd166d3e731bea`.
- Package: `io.homeassistant.companion.android.minimal`; minimum Android SDK **23**.
- Native libraries include **armeabi-v7a** and `libmicrowakeword.so`.

[companion-artifact.json](../companion-artifact.json) records provenance, the published asset digest and inspected package details. The signing certificate was not independently audited. Use the universal APK with ARMv7 support; processor hardware capability does not make an ARM64-only APK compatible with this ROM's userspace.

The minimal flavor **does not require Google Play Services**. GApps and a Google account are unnecessary for this dashboard/Assist route. Some Google-dependent functions, including location tracking and Matter commissioning, are absent. [Official flavor documentation](https://companion.home-assistant.io/docs/core/android-flavors/).

After successful Android boot, enable USB debugging and authorize the project's NAS ADB key on the device. Then use the selected port and complete observed serial:

```bash
python3 scripts/remote.py probe-android --port PORT --serial FULL_SERIAL
python3 scripts/remote.py install-companion --port PORT --serial FULL_SERIAL
```

The USB host is only needed for conversion and app installation. Normal Companion operation uses Wi-Fi.

## Connect to your Home Assistant server

1. Complete Android setup, join the intended Wi-Fi, set time/time zone and check touch, screen and speaker operation. Keep the Show's normal power adapter connected.
2. Open your actual Home Assistant URL from the Show, such as `https://ha.example.com`. This is an example address; replace it with the endpoint reachable from your network. Verify routing, DNS and TLS before changing app settings.
3. Open Companion, select the existing server and log in on the device. On the **960×480** screen, onboarding controls such as manual server-address entry can be below the visible area: **scroll before assuming the control is missing**. A dedicated non-administrator HA user is suitable for a persistent room display. Keep credentials and authorization tokens out of project files, shell history and public screenshots.
4. Load a simple dashboard appropriate for the **960×480** screen. Verify live state updates and a harmless action before adding heavy custom cards.
5. If desired, enable Companion's **Fullscreen** and **Keep screen on** options. Keep screen on applies while the dashboard is active. Test screen sleep/wake and reboot behavior separately; these switches do not establish automatic startup or unattended kiosk operation.

Companion needs **Show → HA HTTP(S), WebSocket and returned media/TTS URL access**. Depending on the endpoint, that is commonly TCP8123 on a private route or TCP443 for HTTPS. Verify that HA-generated audio URLs are reachable from the Show, including their hostnames. A working NAS-side request does not establish the Show's own Wi-Fi route.

The plain Companion path does not require MQTT, ESPHome TCP6053 or VACA TCP10800. Keep any later device-control port within trusted networks. If HA or speech services are remote, local wake-word detection does not make the entire assistant work offline.

## Test Assist with a button first

1. In HA, send a harmless **typed** Assist command to test the selected conversation agent and exposed entities.
2. Open the **Assist dialog** and use its **pipeline dropdown** to select an assistant with working speech-to-text and text-to-speech. Configure the desired language consistently across its stages. This device/dialog selection does not require changing HA's global default assistant. An available pipeline name alone is not evidence that its backend works.
3. In Companion, tap the on-screen Assist/microphone control and grant Android microphone permission. This is the app control, not the Show's Mute/Power button.
4. Speak a short command, inspect the transcript, confirm the intended action and listen for a response. Repeat five times, including a command immediately after a response.
5. If it fails, inspect HA's Assist debug stages to separate capture, recognition, conversation and playback failures before changing wake-word settings.

For Russian or another language, create or select an appropriately configured pipeline and choose it explicitly in the Assist dialog. Native **Companion app → Assist for Android** settings govern Android assistant integration and wake-word behavior; they are distinct from the pipeline dropdown. Keep household-specific pipeline IDs, engine credentials and test transcripts in ignored local records. Existing working speech services can be reused; this project does not require a particular provider or deploy new speech servers.

## Optional hands-free operation

Official Companion documents experimental **on-device microWakeWord** from version 2026.2.3 onward. Open **Settings → Companion app → Assist for Android**, choose Home Assistant as the default digital assistant, enable **Wake word detection**, and select a supplied phrase. Confirm the controls exist in the installed minimal build, then repeat a command already verified with the button. [Official Android Assist instructions](https://www.home-assistant.io/voice_control/android/).

Grant Android microphone permission and, when enabling sustained listening, approve the intended app's background battery exception. Check the actual permission/settings state rather than assuming the prompt succeeded. Test with the dashboard visible and after screen sleep. Keep only one continuous microphone listener active. If wake-word mode makes the app unresponsive, setting Android's default digital assistant to another app or None disables it so button-driven testing can resume.

Documented choices include **Hey Nabu, Hey Jarvis and Hey Mycroft**. Changing the speech pipeline language does not change the wake phrase. Arbitrary custom wake-word import is not established for the pinned Companion build. VACA separately documents importing a trained microWakeWord **`.tflite` + `.json`** pair. [VACA custom files](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Custom-Files).

With local detection, the app processes the wake phrase on the Show and then sends the request to HA and its configured speech services. Whether the complete interaction stays local depends on those services and the server's location.

## Optional View Assist Companion App

For a custom wake phrase or a room display with additional screen/media controls, evaluate **VACA** alongside the working Companion dashboard. Keep Companion wake-word detection off while VACA owns the microphone, and retain any untested voice behavior as an open acceptance item. The researched version is [v0.13.4](https://github.com/msp1974/ViewAssist_Companion_App/releases/tag/v0.13.4), published 2026-09-28. Install its HA integration and Android APK at matching versions, updating the integration first. The additional View Assist integration supplies visual workflows and is separate from VACA's required integration. [VACA setup](https://github.com/msp1974/ViewAssist_Companion_App/wiki/Getting-Started).

VACA uses Android WebView and supports local microWakeWord. Stop Companion's wake-word listener before enabling VACA's. Generic noise suppression or music ducking does not establish stock-Alexa acoustic echo cancellation.

VACA adds **HA → Show TCP10800** by default through Wyoming; use the port actually shown by the app. Show → HA HTTP(S), WebSocket and media access is still needed. Across routed networks, configure the device explicitly if mDNS discovery does not work. Keep that control port private. [Transport implementation](https://github.com/msp1974/ViewAssistCompanionApp/blob/main/app/src/main/java/com/msp1974/vacompanion/wyoming/WyomingTCPServer.kt).

The project can fetch and verify the optional pinned VACA APK, but the core conversion scripts do not install it or deploy its HA integration. On Android 11, the reviewed VACA automatic-start route requires settled onboarding permissions and VACA as the default Home app; Companion can resume the dashboard after the VACA service starts. Follow [the private custom wake-word guide](vaca-private-wakeword.md) for startup limits, the pinned artifact, app-private model placement, static-path exposure, telemetry scope, destructive Sync behavior and threshold semantics. Choosing another OS such as TECHO5 is a separate conversion path, not an Android app installation.

## Acceptance checklist

Keep the actual serial, Wi-Fi details, HA URL, pipeline selection and logs in an ignored private record. Suggested acceptance criteria are engineering targets, not upstream guarantees:

- **Display:** responsive dashboard, live state updates, working touch and a harmless successful action.
- **Button-driven audio:** five consecutive commands with correct transcripts, actions and audible responses.
- **Hands-free:** at least 18 of 20 predefined commands succeed under normal room conditions; record distance, background noise, false activations and latency.
- **Controls:** verify actual microphone mute/unmute, screen wake and camera behavior.
- **Recovery:** after installation is complete, test cold boot, Wi-Fi reconnection and a brief HA/network interruption without manual app repair.
- **Soak:** run for at least 72 hours and retest sound daily; record crashes and reboots, particularly because earlier ROM builds had multi-day audio failures.
- **Optional media:** test camera stills/video and a simple media stream separately; passing voice tests does not establish arbitrary codecs, DRM playback or synchronized music.

If the dashboard stalls, distinguish routing, transport, authentication, WebView and frontend rendering before changing several components. An upstream Echo/WebView report was ultimately resolved as a network failure; it does not establish the cause on another network. [Resolved upstream report](https://github.com/home-assistant/frontend/issues/53819).

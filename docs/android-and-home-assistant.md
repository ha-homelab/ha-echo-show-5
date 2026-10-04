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

## Audio diagnostic limitation on the tested ROM

Do not run `dumpsys media.audio_flinger` on the tested v0.4 build. During this pilot, that diagnostic itself triggered a null-pointer crash in the vendor audio HAL’s `Device::debug()` path. Android restarted the HAL and audio server automatically. This was caused by the inspection command, not evidence explaining the earlier loss of microphone capture; never use the crash as a recovery method. Use ordinary `dumpsys audio` for recorder and mute-state checks. An HA entity showing available, or a running VACA foreground service, does not prove that a microphone recorder is active.

## Screen sleep and Always-on Display

On the tested v0.4 device, both Android `KEYCODE_SLEEP` and VACA's Screen switch initially produced `mWakefulness=Dozing` while **Display Power remained ON**. The ROM resource defaults enabled Always-on Display, and the unset `doze_always_on` setting inherited that default. VACA's **Screen always on** setting is separate: it controls an Activity window's keep-screen-on flag. Replacing the sleep script with VACA's Screen switch did not bypass the Android ambient-display policy. [Android 11 ambient-display settings](https://android.googlesource.com/platform/frameworks/base/+/android-11.0.0_r48/core/java/android/hardware/display/AmbientDisplayConfiguration.java), [pinned VACA screen implementation](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/device/ScreenUtils.kt).

If the same behavior occurs, first read and privately record the existing value. Run these commands only inside an authorized Android shell whose device identity has been verified, with no active call or microphone-handoff session:

```sh
settings get secure doze_always_on
```

The minimal change is:

```sh
settings put secure doze_always_on 0
settings get secure doze_always_on
```

Then send `input keyevent 223`, wait about five seconds, and inspect `dumpsys power` and `dumpsys display`. Require **`Display Power: state=OFF` / `mScreenState=OFF`**. `Dozing` alone and an HA switch reporting off are insufficient: VACA reports interactive state, which is distinct from display power. Send `input keyevent 224` to wake, then verify display ON and `mWakefulness=Awake`. [Android interactive-state distinction](https://developer.android.com/reference/android/os/PowerManager#isInteractive()).

This sequence passed on the test device: after disabling Always-on Display, sleep reported **Dozing with Display Power OFF**, and wake restored **Awake with Display Power ON**. The fixed ADB scripts needed no change. This verifies Android's display-state transition, not deep CPU suspend, long-term screen-off voice reliability or a physical backlight measurement. Notification-triggered ambient pulses are controlled separately by `doze_enabled`; this fix did not change that setting.

For rollback, restore the exact recorded value. If the original readback was **`null`**, restore the absence of the override, rather than writing `1`:

```sh
settings delete secure doze_always_on
```

If the original was an explicit `0` or `1`, restore that value with `settings put secure doze_always_on ORIGINAL_VALUE`. VACA's Screen control remains an optional supported route when its force-lock device-admin permission is active; the Screensaver control only darkens/overlays the screen. Keep the independent wake command available and verify actual display state with either route.

## Complete initial Android setup and enable USB debugging

Finish the Lineage welcome/setup flow. If it offers **Update Lineage Recovery alongside the OS**, leave that option unchecked for this TWRP-based workflow. This is the project's recommendation to retain the existing TWRP recovery, not a stated requirement from the ROM maintainer.

Developer options are initially hidden. Open **Settings → About tablet** (or **About device**), tap **Build number seven times**, then open **System → Advanced → Developer options** and enable **USB debugging**. Connect the data cable and approve the intended NAS host's RSA key on the Show. Choose **Always allow from this computer** only when deliberately authorizing that project's persistent host key.

The scripts cannot approve this on-screen prompt for you. Once authorized, rerun USB inventory if its mode or node changed, then use the complete observed serial for `probe-android` and installation. USB enumeration without an ADB interface before debugging is enabled does not by itself indicate a failed Android boot.

## Persistent Wi-Fi ADB on the tested ROM

The installed **LineageOS 18.1 cronos v0.4** already starts network ADB at boot. Its `/vendor/etc/init/hw/init.mt8163.rc` matches the [upstream boot configuration](https://github.com/amazon-oss/android_device_amazon_mt8163-common/commit/03f23e85e39f49f80df50e6fb1cb52d606256f04): it sets `service.adb.tcp.port` to `5555` and starts `adbd`. The earlier USB recovery demonstrated a working fallback; it did not establish that USB is required after every reboot.

For an explicit persistent fallback, the tested device accepted the following inside an **already authorized, identity-verified Android shell running as UID 2000**. First record the original values privately:

```sh
getprop service.adb.listen_addrs
getprop service.adb.tcp.port
getprop persist.adb.tcp.port
```

Then set and read back the persistent port:

```sh
setprop persist.adb.tcp.port 5555
getprop persist.adb.tcp.port
```

This step required no root, authentication change, ROM edit or SELinux change. It is evidence for this build, not a guarantee that other Android builds allow shell users to write the property. Android 11's daemon uses `service.adb.listen_addrs` when set; otherwise `service.adb.tcp.port` takes precedence, with `persist.adb.tcp.port` used only if that service property is empty. The ROM's own boot action already supplies the service property, so the persistent value is not the sole explanation for network ADB returning. [Android 11 ADB property selection](https://github.com/aosp-mirror/platform_system_core/blob/android-11.0.0_r48/adb/daemon/main.cpp).

**Reboot acceptance passed, 2026-10-03:** after one ordinary Android reboot, TCP5555 and `sys.boot_completed=1` returned in about 46 seconds. A changed boot ID and the complete device serial/`cronos` checks confirmed the same device had rebooted. Both port properties read `5555`; the authorized shell remained UID 2000 with `ro.adb.secure=1` and `ro.secure=1`. A fresh unauthenticated connection received an ADB AUTH challenge. The USB cable was physically present, but no USB commands were used during the test. HA ADB commands also worked after boot without USB intervention. VACA autostarted with one unsilenced recorder. Camera Start on Boot remains off: its process existed, but HTTPS stayed unavailable until its activity was opened manually; Companion home was then launched. Subsequent checks confirmed different fresh camera frames, denied camera microphone permission and idle intercom status without recovery pending. This validates ADB auto-return and the restored baseline, not unattended camera/dashboard startup or recovery after power loss.

Keep the authorized ADB host key and TCP5555 on trusted private networks. Reconnect the existing HA Android Debug Bridge integration and verify device identity before sending commands. If network access fails, retain the [guarded USB fallback](camera-and-intercom.md#manual-recovery-after-an-android-reboot).

**A second unit exposed a separate Wi-Fi recovery limitation.** On the same ROM, the ADB port properties and trusted host authorization survived reboot, but network access missed a 150-second recovery deadline. Its Wi-Fi log recorded `PnoScanListener onFailure: reason: -3 description: not supported` after the screen turned off while disconnected. Waking the screen restarted normal scanning; association and DHCP completed about five seconds later. A later Wi-Fi restart while the screen was off reproduced the unsupported scan errors, and waking it again restored connectivity. The initial failed association remains unexplained. This evidence concerns reconnection while disconnected, not loss of an established connection whenever the screen sleeps.

Distinguish an unavailable Wi-Fi route from an ADB authorization or listener failure. Inspect the selected device's IP address and `dumpsys wifi` through trusted USB before changing ADB settings. On this second unit, keeping the screen awake while AC-powered, settling VACA's permission flow, selecting it as the default Home app and granting its background-execution exception produced a successful follow-up ordinary reboot: network ADB returned in **45.3 seconds without USB commands**, and VACA subsequently reconnected with one unsilenced 16 kHz mono recorder. The configured engine, model, pipeline and threshold survived. Companion's separate dashboard was opened manually afterward.

The AC stay-awake override is `stay_on_while_plugged_in=1`, applied with `svc power stayon ac` only after observing `mPlugType=1`; its recorded previous value was `0`. This is the tested operating workaround, not an isolated proof that this one setting fixed every startup dependency. Restore the operator's own recorded value when rolling it back. Screen-off reconnection, power-loss recovery and long-term stability remain unverified. Do not apply either unit's successful normal-reboot result to every converted device.

For rollback of the added property, restore its exact recorded value; if it was empty, use `setprop persist.adb.tcp.port ''` and read it back. **Clearing this property does not disable the ROM's boot listener**, because the boot action still sets the higher-priority service property. Do not treat that rollback as a permanent network-ADB off switch.

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

Normal Companion operation and the verified network ADB connection use Wi-Fi. Keep the trusted USB host available for conversion, initial authorization and recovery; app installation can use an already authorized, identity-verified ADB connection.

## Connect to your Home Assistant server

1. Complete Android setup, join the intended Wi-Fi, set time/time zone and check touch, screen and speaker operation. Keep the Show's normal power adapter connected.
2. Open your actual Home Assistant URL from the Show, such as `https://ha.example.com`. This is an example address; replace it with the endpoint reachable from your network. Verify routing, DNS and TLS before changing app settings.
3. Open Companion, select the existing server and log in on the device. On the **960×480** screen, onboarding controls such as manual server-address entry can be below the visible area: **scroll before assuming the control is missing**. A dedicated non-administrator HA user is suitable for a persistent room display. Keep credentials and authorization tokens out of project files, shell history and public screenshots.
4. Load a simple dashboard appropriate for the **960×480** screen. Verify live state updates and a harmless action before adding heavy custom cards.
5. If desired, enable Companion's **Fullscreen** and **Keep screen on** options. Keep screen on applies while the dashboard is active. Test screen sleep/wake and reboot behavior separately; these switches do not establish automatic startup or unattended kiosk operation.

Companion needs **Show → HA HTTP(S), WebSocket and returned media/TTS URL access**. Depending on the endpoint, that is commonly TCP8123 on a private route or TCP443 for HTTPS. Verify that HA-generated audio URLs are reachable from the Show, including their hostnames. A working NAS-side request does not establish the Show's own Wi-Fi route.

The plain Companion path does not require MQTT, ESPHome TCP6053 or VACA TCP10800. Keep any later device-control port within trusted networks. If HA or speech services are remote, local wake-word detection does not make the entire assistant work offline.

### Repair an obsolete Companion server address

During this pilot, the existing server's external hostname returned **NXDOMAIN**: that name no longer resolved. An alternate HTTPS address was verified to reach the **same HA instance**, with authenticated HTTPS and secure WebSocket access working. Updating only **External URL** in the existing Companion server entry preserved its authentication. **Internal URL remained unset.** This is a confirmed address repair; it does not establish a working video call or explain every earlier slow frontend load.

Use the following order when Companion cannot connect:

1. Inspect the selected server's current External URL and any Internal URL in Companion's app settings. Check the hostname from the Show's network. NXDOMAIN is a DNS failure; a cached dashboard, a reachable ADB port or another host's successful request does not prove that this URL resolves on the Show.
2. Verify any replacement address belongs to the intended HA instance before using the existing authentication with it. Check DNS resolution, the HTTPS certificate and the served instance. Then verify authenticated HTTPS and **WSS** access; an unauthenticated landing page or HTTP 200 alone is insufficient. Keep credentials and diagnostic payloads private.
3. In **Companion app settings**, select the **existing server** and edit its **External URL** to the verified same-instance HTTPS address. Use the supported settings UI, retain that server entry and save the change. This repair does not require clearing app data, deleting/re-adding the server or changing HA's global URL settings. The tested configuration had no Internal URL; preserve the existing routing policy unless a different local route is deliberately being configured.
4. Reopen the dashboard and confirm fresh state updates and authenticated WebSocket operation through the selected address. Retest media/TTS URLs and the intended call separately. A repaired server connection does not prove camera access, peer connectivity or audible output.

Keep endpoint reachability separate from frontend readiness. The [optional readiness workaround](../integrations/show5-intercom/README.md#optional-companion-readiness-workaround) addresses a measured native handshake delay after the frontend connects. It cannot repair DNS, TLS or authentication failures. Verify those prerequisites before attributing a loading overlay to dashboard performance.

### VACA dashboard says it cannot connect, but the satellite is online

VACA's embedded dashboard uses its own native external-auth session. Its Wyoming
voice connection can remain healthy while that dashboard displays **Unable to
connect to Home Assistant**. Check the foreground application first: this error
can come from VACA even when the official Companion application is not running.

If device-side DNS/TLS/HTTPS work and the VACA satellite is still available in HA,
use **Settings → Devices & services → the intended VACA device → Refresh**.
The equivalent HA action is `button.press` for that device's `button.*_refresh`.
On the Show, a two-finger upward swipe opens VACA Quick Actions; select **Reload**.
The action reloads VACA's configured HA dashboard and repeats external-auth.
It does not restart the voice service, clear credentials or change the assistant.
It may return to the configured dashboard rather than the previously open route.
See the [integration button](https://github.com/msp1974/ViewAssist_Companion_App/blob/v0.13.4/custom_components/vaca/button.py)
and [pinned Android refresh implementation](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/utils/CustomWebView.kt).

**Observed recovery, October 4, 2026 PDT:** the second converted Show had a loaded
VACA integration, working Wyoming connection and reachable HTTPS endpoint, while
its embedded dashboard was stuck during initialization. A page-only reload
restored authenticated HA WebSocket access and rendered the dashboard. A follow-up
page inspection still reported the connection active, and the owner confirmed
that the display worked. The selected FCC
assistant and wake-word settings were preserved, and VACA retained an unsilenced
microphone recorder. This supports a dashboard/session initialization failure;
the original trigger was not established. It is not evidence of a permanent fix
for every reconnection failure. If refresh does not work, investigate transport
and authentication before clearing app data or restarting HA.

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

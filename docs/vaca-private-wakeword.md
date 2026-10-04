# Optional VACA with a private custom wake-word model

This is an optional extension to the confirmed Android/Companion dashboard route. It keeps the official Home Assistant Companion app authenticated for the dashboard and uses **View Assist Companion App (VACA) 0.13.4** for custom microWakeWord detection and the HA satellite connection. Setup evidence and physical acceptance are separate: installing a model or connecting the integration does not establish reliable voice activation.

The current deployment checkpoint is recorded in [validation status](preparation-status.md). This guide deliberately contains no household model names, wake phrases, device identifiers, server addresses, credentials or model files.

## Pinned software

The optional APK is `vaca-0.13.4.apk`, package **`com.msp1974.vacompanion`**, from the [official v0.13.4 release](https://github.com/msp1974/ViewAssist_Companion_App/releases/tag/v0.13.4):

- Size: **120,488,136 bytes**.
- SHA256: **`8769df7bca33c14254a58049a825cf58d3dd7b3272156225662bb4810b9f8f8d`**.
- Official GitHub asset ID: **595157229**.

[vaca-artifact.json](../vaca-artifact.json) records provenance and the published asset digest. It does not represent a separate signing-certificate audit or a reproducible-build claim. Fetch and validate the APK without accessing a device:

```bash
python3 scripts/artifacts.py fetch vaca
python3 scripts/artifacts.py verify vaca
```

Verification checks the pinned size and SHA256, requires an APK container, and validates archive CRCs. The APK remains under ignored `downloads/`. These commands neither install it nor change HA. The core `install-companion` stage still installs the official Companion APK; it is not a VACA installer.

Use VACA's HA integration and Android app at matching versions, updating the integration before the app where an existing installation needs an upgrade. The separate View Assist integration for visual workflows is not the same component as VACA's required integration. Keep any installation procedure explicitly bound to the verified Android device.

This guide's behavior review uses the pinned [Android source](https://github.com/msp1974/ViewAssistCompanionApp/tree/65906aebffd2f39772773b44729b22fd022a1f3c) and [HA integration source](https://github.com/msp1974/ViewAssist_Companion_App/tree/4948528bd016c24c395bf8dc3d86c1c7ec60eb73). A future release requires rechecking the paths and behavior below.

## Network and microphone ownership

VACA requires **HA → Show TCP10800** by default for Wyoming, or the actual port configured in the app. The device still needs access to HA authentication, HTTP(S), WebSocket and returned media URLs. Across routed networks, configure the intended device explicitly rather than assuming mDNS discovery crosses network boundaries. Keep the device listener on a trusted private network.

Keep official **Companion wake-word detection off** while VACA owns continuous microphone capture. Grant VACA's own microphone and background-execution permissions deliberately; Companion permissions do not automatically apply to another package. For voice capture, `RECORD_AUDIO` is required; camera and shared-storage access are optional functionality. Denying optional permissions can nevertheless re-enter this version's onboarding flow at the next launch, so verify the settled denial behavior and startup checks below. Keeping the Companion dashboard authenticated does not require two simultaneous wake-word listeners.

Check the selected VACA wake engine and pipeline independently. Pipeline language affects speech recognition and responses; it does not manufacture a custom wake-word model. Leave the global HA default assistant unchanged when selecting the intended device pipeline.

## Android 11 startup behavior

The reviewed VACA boot flow on Android 11 uses VACA as the **default Home app** for automatic startup after reboot. This is separate from Android's default digital-assistant setting. **Default Home alone is insufficient:** onboarding must also reach voice initialization without waiting for user input. Expect VACA's initial screen after reboot; once its foreground service has started, Companion can be brought to the foreground for the dashboard.

At every activity launch, the pinned code checks both core and optional permissions instead of using a completed-onboarding marker. Missing optional permissions can reopen runtime requests and then the **Write Settings → notification-policy access → device-administrator** flow. Resolve the intended permission choices through supported Android interfaces and inspect the app's requested administrator policy before enabling it. Do not assume one successful foreground launch or denial of a prompt makes the next launch unattended. [Pinned startup check](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/MainActivity.kt#L215), [permission sequence](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/MainActivity.kt#L746).

The tested configuration settles that flow as follows:

- **Microphone:** granted.
- **Camera and shared storage:** denied through Android's **Deny and don't ask again** UI, with the resulting `USER_FIXED` denial independently checked. Do not grant optional access solely to suppress a repeated prompt.
- **Write Settings and notification-policy access:** allowed, so those setup dialogs no longer block initialization.
- **Device administrator:** the reviewed `VACADeviceAdminReceiver` is enabled with its **force-lock-only** policy; it declares no device-wipe policy. Recheck the actual policy if the app version changes.
- **Home and lock screen:** VACA is the default Home app. The test device had no PIN and its non-credential swipe lock was disabled; removing an existing credential lock is not a general requirement of this guide.

With those settings settled, the test device passed **one normal Android reboot without an unlock or manual app launch**. VACA restarted with its selected local model, active microWakeWord engine, foreground service, TCP listener and unsilenced capture path; ADB remained nonroot. Fresh HA reconnection was independently correlated on both sides. Companion then resumed the foreground dashboard while VACA's service and capture remained active in the background. This does not establish power-cycle recovery, physical wake-phrase recognition or multi-day reliability. Use supported Android interfaces to settle denials and verify actual permission/app-op/policy state; do not assume a shell permission command from another Android version is supported here.

No supported service-only boot mode that automatically returns Companion to the foreground was found in the reviewed version. Selecting a Home app or seeing a running service before reboot does not establish recovery afterward: verify normal boot, model selection, engine state, satellite reconnection and the dashboard/service combination explicitly. Physical power-cycle and multi-day reliability remain separate tests.

## Keep model files out of public/static paths

A private microWakeWord model consists of a matching **`.json` descriptor and `.tflite` file**. Keep its originals, checksums, names, training/evaluation material and import records under ignored private storage. Do not commit them or put them in the HA `vaca` content directory.

The pinned integration registers the HA `config/vaca` directory as the **`/vaca` static HTTP path**. Treat files there as accessible without the app's authenticated model-import session, including through any externally reachable HA endpoint. This project's private-model route deliberately avoids that distribution path. [Pinned HTTP registration](https://github.com/msp1974/ViewAssist_Companion_App/blob/4948528bd016c24c395bf8dc3d86c1c7ec60eb73/custom_components/vaca/http.py).

The reviewed alternative places the matching pair directly in VACA's app-private storage under **`filesDir/custom/wakewords/microwakeword/`**, with the correct application ownership, SELinux labels and private permissions. The descriptor's model filename must resolve to its matching local TFLite file. The provider reads descriptors and maps the model from that directory. [Pinned custom provider](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/wakeword/microwakeword/providers/CustomWakeWordProvider.kt), [storage layout](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/utils/CustomFileDownloader.kt).

This is an attended app-private import, not a public download or a generic script bundled here. If the selected LineageOS setup temporarily uses rooted ADB for the import, verify the imported pair's hashes, restore the files' application ownership and SELinux labels, remove staging copies and disable ADB root immediately afterward. Independently verify the final nonroot ADB state and the app's ability to read the pair. Do not leave a root debugging session enabled for daily operation.

**Do not press the explicit Custom Files Sync control for this local-only setup.** The pinned `syncAllCustomFiles()` path clears **all** local custom files before attempting to download the server's advertised set. A model intentionally absent from HA static storage would therefore be removed. Keep a private recovery copy and recheck the selected local model after app updates or data resets. [Pinned sync implementation](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/satellite/SatelliteCustomFilesHandler.kt).

## Telemetry and service scope

Local model-file placement does **not** establish zero telemetry. The pinned Android wake handler calls Firebase event logging with the configured model identifier, threshold and prediction score. No app-level opt-out was found during this review; these source calls identify metadata that may be reported, rather than proving delivery for a particular session. Keep that distinction when assessing a private wake phrase. [Pinned wake-event calls](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/satellite/SatelliteWakeWorkHandler.kt).

The original model files are not published through HA in this workflow, but voice requests still use HA and its configured recognition/conversation/speech services. Whether those services or their telemetry leave the home network depends on the deployment. This guide does not describe a fully offline stack.

## Threshold interpretation and acceptance

The HA threshold control uses a **0–10** scale; the Android app divides it by ten and passes the result through a two-decimal helper. The reviewed helper truncates a Float32 product rather than rounding to nearest: HA **9.4** can become **0.93**, while **9.5** becomes **0.95**. Do not assume arbitrary three-decimal model cutoffs can be represented by this control. These are configuration values, not measured detection accuracies or recommended calibration for every model. [Pinned settings conversion](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/settings/Settings.kt), [HA threshold entity](https://github.com/msp1974/ViewAssist_Companion_App/blob/4948528bd016c24c395bf8dc3d86c1c7ec60eb73/custom_components/vaca/number.py).

The reviewed Android wrapper forwards a model score rounded to two decimals and constructs its own threshold-based detection flag. The satellite handler compares the score against the configured threshold rather than requiring the underlying microWakeWord detector's original rolling-buffer `detected` flag. Do not assume another microWakeWord runtime's rolling-window calibration transfers directly to this version. [Pinned engine wrapper](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/wakeword/WakeWordEngine.kt), [satellite decision](https://github.com/msp1974/ViewAssistCompanionApp/blob/65906aebffd2f39772773b44729b22fd022a1f3c/app/src/main/java/com/msp1974/vacompanion/satellite/SatelliteWakeWorkHandler.kt).

Verify the application loads the intended local pair, the selected pipeline is connected, and the experimental threshold actually reaches the device. These are deployment checks. If nobody is available to speak near the physical device, record physical acceptance as **pending** rather than interpreting silence, ambient events or server connectivity as success.

Later, perform deliberate near-device trials: intended wake phrase, listening indication, a harmless command, correct transcript/action and an audible response. Include negative phrases, normal background audio, screen sleep and recovery after interruption. Keep any diagnostic recordings, model names and transcripts private. Complete the [multi-day acceptance checklist](android-and-home-assistant.md#acceptance-checklist) before claiming room-ready reliability.

# Android permissions and limits on the converted Show

Reviewed **2026-10-29** for **Echo Show 5 Gen2 / cronos, LineageOS 18.1 / Android 11**. This is a capability and configuration guide, not a record that every optional permission has been granted. A manifest declaration, an enabled Android setting, a live HA entity and a successful physical test are four different kinds of evidence.

The useful expansion path is to give a selected application the access needed for a defined room function, then verify the complete function. More permissions do not create missing sensors, add codecs, turn an ordinary application into a system service or solve contention between two microphone users.

See also [remote administration](android-remote-access.md), [room capabilities](room-endpoint-capabilities.md), and the existing [Android operating guide](android-and-home-assistant.md).

## Installed permission checkpoint

The read-only inventory on **2026-10-29** found the following on the two installed Shows. These observations do not enable anything new.

| Application/access | Show 1 | Show 2 | Consequence |
| --- | --- | --- | --- |
| VACA `0.13.4+myshka.10-sip.1` / `7010` | Microphone granted; camera and external-storage permissions denied | Same | Existing voice capture does not require enabling VACA camera or broad storage access. |
| Native Show SIP `0.1.0` | Microphone granted; no camera permission in the audio-only package | Same | Keep it an audio client; video still belongs to another application. |
| Jitsi Meet `26.0.0` | Camera and microphone granted | Same | A new blanket grant is not the missing step for Jitsi video/audio. Resource ownership and call transport still need to work. |
| Companion `2026.8.4-minimal` | Camera and microphone granted | Camera and microphone denied | Button-driven Companion recording on Show 2 would need its own grant. This does not require changing the working VACA listener. |
| Companion location | Fine, coarse and background location denied | Same | Do not assume location-dependent sensors or discovery work merely because Companion is installed. |
| Accessibility and notification listeners | Both enabled-service settings `null` | Same | No optional service is currently selected through these settings. Installing a consumer and enabling it would be a new feature. |
| Device administration | VACA device administrator enabled; no device-owner/profile-owner entry in the captured policy output | Same | VACA is not shown as an enterprise device owner. Its admin role is not general system privilege. |

The legacy setting `install_non_market_apps=1` was present, but it is **not evidence that every installer is trusted on Android 11**. That decision must be checked for the chosen source application. The current inventory also showed exactly one runtime Android sensor, **LIGHT**, on each device despite broader feature declarations. Additional permission grants do not make the advertised but unenumerated motion sensors usable. See the [installed capability snapshot](installed-capabilities.md) for the full dated evidence and its limits.

## Keep the three identities separate

- **An Android application** runs under its own Linux UID. This includes a terminal or SSH server installed as an ordinary app. Its shell normally sees that app's files and explicitly shared storage, not every other app's private files.
- **An authorized ADB session** runs as the Android shell user in this deployment. The earlier verified UID is **2000**, not root. The platform grants it useful administration and diagnostic interfaces, but it is not equivalent to an unrestricted Linux administrator.
- **HA authorization** is separate again. A phone action or dashboard control can require an HA administrator even when the Show is signed into HA with a display account. Granting an Android permission does not change that HA role.

Android's [application sandbox](https://source.android.com/docs/security/app-sandbox) and [permission types](https://developer.android.com/guide/topics/permissions/overview) explain the first boundary. Signature permissions also depend on the signing certificate: the SIP pilot's VACA audio-lease interface deliberately uses a signature permission. Re-signing one of those APKs with an unrelated certificate is not a way to extend the interface. See the [SIP pilot change](https://github.com/ha-homelab/ha-echo-show-5/pull/115).

## Access that can enable a useful room function

The settings names below describe the Android 11 concepts. Lineage's exact menu wording can differ. For optional applications, check both what the package requests and what Android has actually allowed before changing anything.

| Access | Useful function | Boundary and deployment decision |
| --- | --- | --- |
| Microphone / `RECORD_AUDIO` | Wake words, a spoken Assist request, SIP or Jitsi speech | Required by the current voice path. Grant it to applications that deliberately take an audio turn. Permission alone does not make two recorders coexist correctly. Keep the existing VACA/SIP lease and restore VACA after calls. |
| Camera / `CAMERA` | A deliberately started video call or camera server | Grant to the chosen video application. The installed native SIP pilot is audio-only and explicitly removes camera permission. A second camera consumer needs a verified release/handoff; a stopped stream is not proof the camera was released. |
| Notifications and notification channels | Incoming-call alert, timer, doorbell event or HA action buttons | On **Android 11**, there is no `POST_NOTIFICATIONS` runtime prompt; that prompt starts at Android 13. An application may still declare the permission for newer OS versions. Check application/channel settings and Do Not Disturb behavior instead of hunting for the newer prompt. |
| Notification access / listener service | A selected app can react to another app's posted/removed notifications on the same device | Optional. Sending HA notifications to the Show does **not** require reading every other app's notifications. Enable a listener only for a concrete cross-app workflow, with filtering in its implementation. |
| Usage access / `PACKAGE_USAGE_STATS` | A local supervisor can tell which application was used or is occupying the display | Optional telemetry. It does not grant input injection, microphone ownership or the ability to terminate arbitrary apps. App-owned lifecycle state is often a better source for our own apps. |
| Modify system settings / `WRITE_SETTINGS` | A room controller can set brightness or supported system display settings | Suitable for the application that owns display policy. This is not `WRITE_SECURE_SETTINGS`, root, or access to every Lineage setting. Keep one brightness authority; otherwise HA, automatic brightness and local code can undo one another. |
| Display over other apps / `SYSTEM_ALERT_WINDOW` | A purposeful floating control or room-state overlay | Optional and unnecessary for an ordinary fullscreen clock. It does not grant access to the underlying app's content. A full-screen incoming-call notification is a different mechanism; do not add overlay access simply because a call UI exists. |
| Battery optimization exception | Improve continuity of a selected listener or persistent connection | Use for the service whose continuous operation is required. It is not an exemption from all Android lifecycle restrictions, cannot fix a broken Wi-Fi driver, and does not guarantee restart after a crash or reboot. |
| Install unknown apps / `REQUEST_INSTALL_PACKAGES` | Let the chosen installer initiate a local APK update | Optional and **per installer** on Android 11. Trusting a browser does not trust every file manager. The existing authorized ADB installation route is separate and does not require enabling this for all apps. |
| Storage access | Import a playlist or wake-model file; export a selected diagnostic bundle | Prefer the system file picker, app-private files and app-specific external storage. Broad storage access is not required for a network stream. It does not expose other apps' private internal directories. |
| Location/Bluetooth access | BLE discovery, a supported nearby-device workflow or network-related metadata | Evaluate only for a feature that uses it. Android 11 uses the older Bluetooth/location permission model; Android 12's Nearby Devices permissions are not interchangeable instructions. A location permission cannot add a GNSS receiver, and BLE scanning is not automatically an HA Bluetooth proxy. |
| Accessibility service | A deliberate assistive interaction that supported app actions cannot provide | Optional, broad and sensitive. It may inspect exposed UI and perform configured actions. Prefer our own explicit HA services, app intents and media controls for automation; coordinate-based UI automation becomes fragile after layout or language changes. |

The platform references behind this table are [camera/microphone foreground services in Android 11](https://developer.android.com/about/versions/11/privacy/foreground-services), [notification permission versioning](https://developer.android.com/develop/ui/compose/notifications/notification-permission), [notification listeners](https://developer.android.com/reference/android/service/notification/NotificationListenerService), [usage statistics](https://developer.android.com/reference/android/app/usage/UsageStatsManager), [special app access](https://developer.android.com/training/permissions/requesting-special), [system-setting access](https://developer.android.com/reference/android/provider/Settings.System#canWrite(android.content.Context)), [Doze and standby](https://developer.android.com/training/monitoring-device-state/doze-standby), [per-source installation trust](https://developer.android.com/studio/publish#unknown-sources), [Android 11 storage](https://developer.android.com/about/versions/11/privacy/storage), [Bluetooth permissions](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions), and [accessibility services](https://developer.android.com/guide/topics/ui/accessibility/service).

### Camera and microphone need lifecycle code, not an "always allow" workaround

For apps targeting Android 11 or later, foreground services that use these devices must declare the appropriate service types. Starting such a service from the background does not by itself permit camera/microphone capture. The existing SIP controls therefore bring the phone activity forward before deliberate dialing or answering. A granted microphone permission or persistent notification does not prove that the recorder is receiving sound.

Android 11 also supports one-time grants and can reset runtime permissions on unused applications. A service should detect a lost grant and expose a clear recovery action. It should not repeatedly launch a denied permission dialog or treat a remembered preference as proof of current authorization. [Android 11 permission changes](https://developer.android.com/about/versions/11/privacy/permissions).

The hardware privacy state is another independent layer. The cronos Mute/Power coupling and possible camera initialization effect are documented in the [ROM operating notes](android-and-home-assistant.md#rom-capabilities-and-limitations). Software permissions do not override that physical state. For a video-only camera server, keep microphone permission denied until an explicit audio feature needs it.

### "Unknown publisher" is not one global unlock

An installation failure, a download failure and a playback failure require different checks:

1. **Download:** HTTP 403 is a server/access-policy response. DNS and TLS/time errors occur at different stages. Changing Android installer trust does not repair any of these.
2. **Install:** check the selected installer's trust, APK integrity, available storage, compatible minimum SDK/ABI, and the signing identity required to update an existing package.
3. **Run:** verify the application has an Android 11-compatible code path and its required runtime/special access.
4. **Play:** check the media URL, authentication, container, codec and any DRM separately.

After a one-off browser/file-manager install, its installation access can be disabled again. Do not remove the existing working app or clear its data to resolve an unexplained signing mismatch; that can discard HA pairing and local settings. [Package install authorization](https://developer.android.com/reference/android/content/pm/PackageManager#canRequestPackageInstalls()).

## Device admin, device owner and kiosk are different choices

VACA's optional **device administrator** role supports its declared device-management actions, such as force-lock for screen control. It does not convert the application into a root daemon or confer every enterprise policy. Android has deprecated some legacy device-admin policies; check the specific API rather than assuming all historical admin features remain usable. [Device administration](https://developer.android.com/work/device-admin).

A **device owner/DPC** is a larger managed-device provisioning decision. It can implement policies and an allowlisted multi-app kiosk, but it is not a routine extra permission to add to these already provisioned, signed-in Shows. Standard fully managed provisioning expects an unprovisioned device and can involve a reset. The current project does not need to discard working HA pairing merely to obtain a fullscreen clock or app launcher. Evaluate a DPC on a separate test device with a complete restore plan if future unattended-fleet requirements justify it. [Device-owner provisioning API](https://developer.android.com/reference/android/app/admin/DevicePolicyManager#ACTION_PROVISION_MANAGED_DEVICE).

Ordinary **screen pinning**, **default Home application**, and enterprise **lock task mode** must not be treated as synonyms. A default Home app supplies the destination of the Home action; it does not prove that every service is healthy. Screen pinning can be exited by the user. DPC-managed lock task mode restricts the allowed applications and may hide normal recovery navigation, so its exit and service procedure must be designed first. [Lock task mode](https://developer.android.com/work/dpc/dedicated-devices/lock-task-mode).

## Limits a permission cannot remove

| Limit | What to verify before promising the function |
| --- | --- |
| Installed userspace ABI | Use APKs/libraries compatible with the actual advertised ABI, currently the project's ARMv7 route. A 64-bit-capable chip does not make an ARM64-only APK install into a 32-bit userspace. [Android ABIs](https://developer.android.com/ndk/guides/abis). |
| Android API level | Android 11 is API 30. A package with a higher `minSdk` needs an older supported version or a compatible build, not more permissions. A high `targetSdk` is a different field and is not itself the minimum OS version. |
| Sensor hardware/HAL | Check `SensorManager` enumeration, units, observed changes and freshness. A listed Android feature or permission is not evidence of a working lux/proximity/temperature sensor. Screen brightness is an output setting, not an ambient-light measurement. [Sensor framework](https://developer.android.com/develop/sensors-and-location/sensors/sensors_overview). |
| Media decoder/encoder | Inspect `MediaCodecList` and test the exact video profile, resolution, frame rate and concurrent workload. A decoder list alone does not establish sustained low-latency playback. [Codec enumeration](https://developer.android.com/reference/android/media/MediaCodecList). |
| DRM and streaming-service eligibility | Check the DRM plugin/security level and the service's own requirements. Installing an app or granting storage permission does not restore missing DRM keys, hardware trust or service certification. [MediaDrm](https://developer.android.com/reference/android/media/MediaDrm). |
| Boot and restart behavior | `RECEIVE_BOOT_COMPLETED` only supplies a lifecycle event to implemented code. It does not create a supervisor, repair Wi-Fi, guarantee a UI launch, or guarantee access to credentials before first unlock. Direct Boot requires suitable components and device-protected storage. [Direct Boot](https://developer.android.com/privacy-and-security/direct-boot). |
| WebView or app lifecycle | A running process can still display a stale page, have a failed websocket or lack an active recorder. Health checks should verify the actual function and use bounded recovery rather than repeatedly restarting every app. |
| Shared audio/camera resources | Permissions can be granted to several apps while only one usable capture path is available. The VACA/SIP lease is a specific cooperating-app protocol. Legacy Jitsi/intercom does not automatically participate in it. |

The ROM's documented permissive SELinux state does not erase Linux UID isolation, Android permission checks, app-side authorization or missing drivers. Treat it as a port limitation, not as a reason to assume arbitrary privileged access. Likewise, the documented artificial battery reading and disabled deep sleep make generic phone battery/presence heuristics unreliable here.

## A reversible rollout record

For each proposed feature, keep a private before/after record with the package name, package version/signing identity, requested permission, actual grant or special-access state, relevant app setting, reason, functional test and rollback. Report public conclusions without copying tokens, full device serials, notification contents or private application data into Git.

A useful read-only baseline contains the OS/API/ABI, application versions, active Home/assistant roles, requested and granted permissions, app-operation state, device-admin/owner state, notification channels, battery exceptions and actual sensor inventory. Use the selected, identity-verified ADB route. Follow the repository's diagnostic exclusion: **do not run `dumpsys media.audio_flinger` on this ROM**; its vendor debug path previously crashed the audio HAL. `dumpsys audio` and explicit recorder/stream checks are separate, supported observations in the existing runbook.

Apply one feature to one Show first, then test entry, exit, interrupted execution and restoration of the clock and VACA. Rollback normally means restoring the recorded per-app setting or revoking the added special access. Device-admin removal must precede uninstall when that role requires it. Clearing app data, removing a paired application, changing a signing key, provisioning device owner, or replacing firmware is not an ordinary permission rollback.

## Recommended order

1. **Keep the working identity and lifecycle foundation.** Preserve authenticated ADB, app signing, current HA pairing, the Home app and the existing voice/call handoff.
2. **Expose health and proven sensors through HA.** This is usually more useful than opening another daemon, and does not need broad notification/accessibility access.
3. **Add intentional controls to our apps.** Prefer named actions for app launch, media, brightness and return-to-clock, with state acknowledgement and an exit path.
4. **Add optional access only with its implementation.** Notification listeners, usage access and overlays are candidates for specific workflows; a grant with no consumer adds no function.
5. **Evaluate managed kiosk separately.** Adopt device-owner policy only if ordinary Home/fullscreen behavior cannot satisfy a written operational requirement. Keep the two functioning room endpoints usable while that experiment is evaluated.

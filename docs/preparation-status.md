# Validation status

Public validation snapshot: **2026-10-02**. Device serials, household inventory, network addresses, credentials, raw logs and private backup records are deliberately excluded. Each operator must collect their own identity and backup evidence.

## Completed

- The genuine **amonet-cronos 2.0.1** archive passed ZIP CRC, safe-path, model metadata and all **31** extracted-file checksum checks. Its locally computed archive digest is recorded in [amonet-artifact.json](../amonet-artifact.json); it is not an independently published signature.
- **LineageOS 18.1 cronos v0.4**, `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`, passed the published digest, archive CRC and `pre-device=cronos` checks.
- **Home Assistant Companion 2026.8.4 minimal** passed its GitHub asset digest and archive CRC checks. Its actual manifest requires SDK23 or newer and includes ARMv7 native libraries; the selected Android 11 ROM uses SDK30.
- The host tools ran on a physical **Synology DS620slim, DSM 7.3.2, Linux 4.4.302+, x86_64**, with host Python **3.8.15**. The dedicated Debian container supplied ADB **1.0.41 / 29.0.6-debian**, diagnostic fastboot **29.0.6-debian**, and Python **3.11.2**.
- The release's modified fastboot **28.0.0 rc1-eng.chaosm.20190910.064622** passed executable, library and launcher checks in a nonroot container without USB or network access. The current per-host validator also passed on the actual NAS, executing a private RAM copy while keeping the reviewed source mount read-only. Its machine-specific validation record remains private. The exploit retains this modified binary; the standard fastboot tool is only for diagnostics.
- A stock physical device identified itself as **CRONOS**, with `unlock_status=false` and LK **44072a3-20240709_162755**. After the attended amonet procedure, independent ADB probes confirmed `ro.product.device=cronos`, `ro.build.product=cronos` and `ro.twrp.version=3.7.0_9-0` with matching complete device identity. USB transitioned from **0bb4:0c01** to **18d1:4ee2**.
- Temporary group read/write permissions on the selected DSM USB node allowed nonroot operation; the wrapper restored the original mode afterward. Explicit `0700` permissions on private ADB directories resolved inherited Synology ACL restrictions.

## Verified backup and installation

**Raw off-device backup capture and verification completed on the tested cronos device.** All three images—the eMMC user area, `boot0` and `boot1`—matched their observed lengths and device/NAS SHA256 values. Both GPT header and entry-array CRCs, partition bounds and the observed partition mapping passed validation, and the completed private manifest was saved on the NAS.

The physical device reported unencrypted Data but insufficient internal space for a staged TWRP file backup. Capture therefore streamed directly to private NAS storage while block-backed filesystems were unmounted. A second private workstation copy also passed full image hashing and GPT verification against the NAS capture.

This capture is post-unlock, excludes RPMB, and does not establish a tested stock restoration procedure. Partial images and a running capture process do not satisfy the backup gate. The runbook requires successful size, device/host SHA256, GPT and partition-map checks before formatting or installation.

The attended **Format Data**, subsequent Data wipe (which also formatted Cache), and System wipe completed. Fresh recovery evidence showed successful `mke2fs` and `e2fsdroid` return codes and new ext4 filesystem UUIDs. Empty Data and Cache each reported approximately 1% usage. Before the System wipe, TWRP's System write restriction was explicitly cleared: `remountrw` changed `tw_mount_system_ro` from `2` to `0`.

The staged ROM's device-side SHA256 matched the pinned artifact. **LineageOS installation then completed in TWRP:** the updater returned `0`, wrote **280,721 of 280,721 expected blocks** (**1,149,833,216 bytes**), and reported an installation time of **67 seconds**. Separate inspection confirmed that the first **8,298,496 bytes** of the installed boot partition matched the ZIP's boot image, SHA256 `848c0934580c5fdd61e2ed641cca45505763880074e921266f7324f86d5b4e2d`.

The installed system uses a **system-as-root** layout. Mounted at `/system` in recovery, its build properties are at `/system/system/build.prop`; these independently report **Android 11**, device **cronos**, and **LineageOS 18.1-20260905-UNOFFICIAL-cronos**. The embedded build date differs from the release ZIP filename's date; the exact pinned artifact and hash were retained.

## Current checkpoint

The required post-installation **final Format Data** completed. Fresh recovery evidence showed successful `mke2fs` and `e2fsdroid` return codes; independent inspection confirmed a new ext4 filesystem UUID, approximately **7.7 MiB used of 3.7 GiB** (1%), and only `lost+found` and `media` in Data.

**First Android boot is confirmed.** The operator completed the Lineage welcome/setup flow, enabled USB debugging and explicitly authorized the intended persistent NAS ADB key on the device. The earlier USB session without an ADB interface was superseded by an authorized Android ADB connection. Live reads confirmed **`sys.boot_completed=1`**, **`device_provisioned=1`** and **`user_setup_complete=1`**. The running OS reported **Android 11** and **LineageOS 18.1-20260905-UNOFFICIAL-cronos**.

The guarded `install-companion` action then passed its complete Android identity probe: **cronos**, **Android 11**, **LineageOS 18.1** and completed boot. Installation of the pinned **Home Assistant Companion 2026.8.4 minimal APK** returned **`Performing Streamed Install`** followed by **`Success`**. Independent installed-package inspection through `dumpsys` confirmed **versionName `2026.8.4-minimal`**, **versionCode `24228`**, **minSdk `23`** and **targetSdk `37`**.

**Companion login and authenticated dashboard rendering are confirmed.** The operator signed in on the device, and the existing dashboard displayed household entity states without changing the global dashboard configuration. Read-only server checks confirmed an enabled Companion device registration, its device-tracking and notification entities, and a healthy server-side HA WebSocket session.

Home Assistant was selected as Android's default digital assistant through the OS interface; the configured assistant component was independently verified as `AssistVoiceInteractionService`. Companion's **Fullscreen** and **Keep screen on** settings were visibly enabled. Keep screen on applies while the dashboard is active; automatic startup and unattended kiosk behavior remain separate acceptance items.

The operator granted the app's background battery exception and microphone permission through Android's interfaces. A separate device-idle whitelist check confirmed the battery exception. A **Russian-language Assist pipeline** was available on the server and selected in the device's Assist dialog, with the selected dropdown state verified. The server's global default assistant was unchanged.

**Controlled physical voice acceptance remains pending.** Permissions, assistant selection and a healthy server connection do not establish successful microphone capture, audible responses, wake-word reliability or multi-day stability. No ambient capture or private transcript is treated as an acceptance test.

## Optional custom wake-word deployment

**VACA 0.13.4 is installed and its satellite connection is established.** The APK passed the pinned size/hash checks. Its matching HA integration was installed, and HA returned healthy after one restart. The satellite reports **idle** with the selected Russian-language pipeline. The official Companion dashboard remains authenticated, and its own continuous wake-word listener is off.

The custom JSON/TFLite pair was placed only in VACA's app-private storage. File hashes, application ownership and SELinux labels were checked. The intended private model and **microWakeWord** engine were selected; HA's experimental threshold is **9.9**, corresponding to **0.99** in the app. Android reports the foreground service and TCP10800 listener, **`MICROWAKEWORD` engine status `Started`**, and wake handler **`RUNNING`**. These establish deployment state, not physical recognition accuracy.

Temporary rooted debugging was disabled after import; an independent ADB identity check returned the nonroot shell UID **2000**. The previous display timeout was restored. Microphone permission is granted; optional camera and shared-storage permissions are denied for this voice-only route.

**Onboarding permission state and one unattended normal Android reboot are verified.** Camera and shared-storage permissions remain denied with Android's **`USER_FIXED`** state after the actual **Deny and don't ask again** UI flow; microphone access is granted. Write Settings and notification-policy access are allowed. The active VACA device-administrator receiver's reviewed policy is **force-lock only**, with no wipe policy. The test device had no PIN configured; its non-credential swipe lock was disabled for the unattended Home-app route. The foreground service was active after these choices were settled.

This permission state matters because VACA checks both core and optional permissions at each activity launch. Default Home alone does not bypass the request flow. On Android 11, the reviewed automatic-start route uses VACA as the default Home app with onboarding settled before voice initialization. With those settings settled, a normal Android reboot completed **without an Android unlock or manual app launch**. Live checks confirmed completed boot, an automatically started VACA process, its foreground service and TCP10800 listener, the intended local model, microWakeWord **`Starting` → `Started`**, and handler **`RUNNING`**. The microphone capture path reported active and unsilenced, no fatal application exception was found, and ADB remained the nonroot shell UID **2000**.

This verifies one normal reboot, not a power-cycle or physical wake-phrase test. Fresh HA reconnection was verified using corresponding live connection evidence on Android and the HA side, together with post-boot application traffic. Companion was returned to the foreground while VACA's foreground service and active, unsilenced microphone capture continued in the background. The intended permission choices, nonroot ADB state and restored display setting were rechecked. No supported service-only startup mode that automatically foregrounds Companion was found. Physical wake-word acceptance and the 72-hour soak remain pending.

Model files, phrases, household identifiers and deployment records are excluded from this public repository and HA's `/vaca` static directory. This does not imply an absence of app telemetry: the reviewed code contains Firebase wake-event calls with a model identifier and score, and no app-level opt-out was found. See [the private-model guide](vaca-private-wakeword.md) for telemetry scope, the pinned source review, destructive Sync behavior and threshold semantics.

## Script checks

The expanded preparation, raw-backup and attended-operation suite passed **all 63 tests on both the workstation and the NAS's Python 3.8.15**. This includes fail-closed readback checks for the new System-write stage. The CI workflow runs the same synthetic suite on **Python 3.8 and 3.11**, without firmware downloads or device access.

Six additional synthetic VACA artifact tests pass locally, bringing the local total to **69**. They cover APK type and CRC validation, CLI selection, manifest-based downloading and rejection of modified bytes; they do not run the APK or contact a device. The last recorded NAS run remains the 63-test suite; CI is configured to run the complete current suite on both supported Python versions.

The tests exercise serial and model rejection, ambiguous USB selection, recovery identity, neighboring conversion locks, artifact type/model validation, audited package changes, host-image binding, backup completion evidence, split/archive structure, raw capture integrity and guarded operation behavior. Synthetic fixtures establish validation behavior; they do not establish successful hardware restoration.

See [script review](script-review.md) for resolved findings and [release audit](release-audit.md) for upstream package observations. Detailed device records belong under ignored `private/`, `logs/` and `backups/`, not in the public repository.

## Remaining acceptance

1. Run deliberate wake-word and button-driven voice tests, checking recognition and audible responses rather than deployment status alone.
2. Test a harmless dashboard action, screen behavior and recovery after a power cycle or network interruption.
3. Complete the 72-hour checks in [the HA guide](android-and-home-assistant.md).

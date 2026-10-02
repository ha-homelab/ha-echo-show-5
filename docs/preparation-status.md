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

## Script checks

The expanded preparation, raw-backup and attended-operation suite passed **all 63 tests on both the workstation and the NAS's Python 3.8.15**. This includes fail-closed readback checks for the new System-write stage. The CI workflow runs the same synthetic suite on **Python 3.8 and 3.11**, without firmware downloads or device access.

The tests exercise serial and model rejection, ambiguous USB selection, recovery identity, neighboring conversion locks, artifact type/model validation, audited package changes, host-image binding, backup completion evidence, split/archive structure, raw capture integrity and guarded operation behavior. Synthetic fixtures establish validation behavior; they do not establish successful hardware restoration.

See [script review](script-review.md) for resolved findings and [release audit](release-audit.md) for upstream package observations. Detailed device records belong under ignored `private/`, `logs/` and `backups/`, not in the public repository.

## Remaining acceptance

1. Run controlled button-driven voice tests and verify both recognition and audible responses.
2. Test a harmless dashboard action, optional wake-word behavior and recovery after interruptions; verify screen and startup behavior separately.
3. Complete the multi-day acceptance checks in [the HA guide](android-and-home-assistant.md).

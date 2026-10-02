# Validation status

Public validation snapshot: **2026-10-02**. Device serials, household inventory, network addresses, credentials, raw logs and private backup records are deliberately excluded. Each operator must collect their own identity and backup evidence.

## Completed

- The genuine **amonet-cronos 2.0.1** archive passed ZIP CRC, safe-path, model metadata and all **31** extracted-file checksum checks. Its locally computed archive digest is recorded in [amonet-artifact.json](../amonet-artifact.json); it is not an independently published signature.
- **LineageOS 18.1 cronos v0.4**, `lineage-18.1-20260904-UNOFFICIAL-cronos.zip`, passed the published digest, archive CRC and `pre-device=cronos` checks.
- **Home Assistant Companion 2026.8.4 minimal** passed its GitHub asset digest and archive CRC checks. Its actual manifest requires SDK23 or newer and includes ARMv7 native libraries; the selected Android 11 ROM uses SDK30.
- The host tools ran on a physical **Synology DS620slim, DSM 7.3.2, Linux 4.4.302+, x86_64**, with host Python **3.8.15**. The dedicated Debian container supplied ADB **1.0.41 / 29.0.6-debian**, diagnostic fastboot **29.0.6-debian**, and Python **3.11.2**.
- The release's modified fastboot **28.0.0 rc1-eng.chaosm.20190910.064622** passed executable, library and launcher checks in a nonroot container without USB or network access. The exploit retains this modified binary; the standard fastboot tool is only for diagnostics.
- A stock physical device identified itself as **CRONOS**, with `unlock_status=false` and LK **44072a3-20240709_162755**. After the attended amonet procedure, independent ADB probes confirmed `ro.product.device=cronos`, `ro.build.product=cronos` and `ro.twrp.version=3.7.0_9-0` with matching complete device identity. USB transitioned from **0bb4:0c01** to **18d1:4ee2**.
- Temporary group read/write permissions on the selected DSM USB node allowed nonroot operation; the wrapper restored the original mode afterward. Explicit `0700` permissions on private ADB directories resolved inherited Synology ACL restrictions.

## Current checkpoint

**Raw off-device backup capture and verification completed on the tested cronos device.** All three images—the eMMC user area, `boot0` and `boot1`—matched their observed lengths and device/NAS SHA256 values. Both GPT header and entry-array CRCs, partition bounds and the observed partition mapping passed validation, and the completed private manifest was saved on the NAS.

The physical device reported unencrypted Data but insufficient internal space for a staged TWRP file backup. Capture therefore streamed directly to private NAS storage while block-backed filesystems were unmounted. A second private workstation copy was transferring at this checkpoint.

This capture is post-unlock, excludes RPMB, and does not establish a tested stock restoration procedure. Partial images and a running capture process do not satisfy the backup gate. The runbook requires successful size, device/host SHA256, GPT and partition-map checks before formatting or installation.

The first attended **Format Data** stage also completed: fresh recovery evidence showed successful `mke2fs` and `e2fsdroid` return codes, a new ext4 filesystem UUID, and empty Data at approximately 1% usage. The full wipe/install sequence is still incomplete. There is **no recorded completion** of ROM installation, Android boot, Companion installation, or physical Home Assistant audio/display acceptance. Server-side Assist checks are distinct from microphone and speaker tests on the Show.

## Script checks

An earlier suite of **27 tests passed on both the workstation and the NAS's Python 3.8.15**. The expanded preparation, raw-backup and attended-operation suite subsequently passed **60 tests on the workstation**. The current expanded NAS run is not recorded in this checkpoint; CI also runs the synthetic suite on Python 3.8 and 3.11 without firmware downloads or device access.

The tests exercise serial and model rejection, ambiguous USB selection, recovery identity, neighboring conversion locks, artifact type/model validation, audited package changes, host-image binding, backup completion evidence, split/archive structure, raw capture integrity and guarded operation behavior. Synthetic fixtures establish validation behavior; they do not establish successful hardware restoration.

See [script review](script-review.md) for resolved findings and [release audit](release-audit.md) for upstream package observations. Detailed device records belong under ignored `private/`, `logs/` and `backups/`, not in the public repository.

## Remaining acceptance

1. Complete the second private backup copy and retain its matching manifest.
2. Perform the attended TWRP format/wipe/install sequence, checking fresh operation evidence and resulting filesystems.
3. Boot Android, confirm the actual build and authorize USB debugging deliberately.
4. Install Companion, log in to the operator's HA server, and test display, button-driven voice, optional wake word and recovery after interruptions.
5. Complete the multi-day acceptance checks in [the HA guide](android-and-home-assistant.md).

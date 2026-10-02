# Script review and verification boundaries

This document records review findings for the staged conversion tools. Reviews used local synthetic fixtures and static inspection unless a hardware result is explicitly listed in [validation status](preparation-status.md). It is not a claim of successful restoration or completed Android conversion.

## Resolved findings

**Backup integrity needed more than hashes and filenames.** An early validator accepted arbitrary bytes named like a Boot/System/Data backup and did not reject missing split segments. Backup creation also lacked positive completion evidence for the particular TWRP operation. The revised checks require fresh completion evidence, hash the saved recovery log, verify contiguous split sets, inspect the Android boot image structure, validate gzip integrity and read archive contents. Corrupt and incomplete fixtures are rejected. A valid synthetic backup passes, but hardware restoration remains untested.

**Artifact type needed validation independent of its filename.** An early artifact path could name a hash-matching `.img` and bypass ZIP/model inspection. Artifact verification now enforces the expected `.zip` or `.apk` container for its kind and requires `pre-device=cronos` for the ROM. The bypass fixture is rejected.

**DSM USB and ADB-directory permissions needed explicit handling.** The selected node's existing group receives temporary read/write permissions only for the operation, and its original mode is restored when the same device/node remains present. Replacement-node checks avoid changing a newly enumerated node. Private ADB host directories receive explicit `0700` permissions to address inherited Synology ACLs. The container stays nonroot and receives a single selected USB node; no whole-bus or privileged-container fallback is used.

## Current safeguards

- Select an exact physical port and complete observed serial; recheck identity and USB-node stability before each command.
- Require a supported cronos product and the proper stock FASTBOOT, TWRP or completed Android state for that stage.
- Refuse concurrent Echo operations through container checks and a project operation lock.
- Verify the genuine amonet archive, all extracted files, model metadata and the locally validated host image before unlock.
- Verify artifact type, size, hash, archive CRC and ROM model. Rehash the staged ROM on the device before installation.
- Revalidate a saved off-device backup before destructive preparation or ROM installation.
- Keep binary raw capture outside text-decoding command helpers. Validate exact lengths, source and saved-image hashes, both GPT CRCs and the partition map.
- Save operation-specific recovery evidence privately. Require deliberate typed action/serial confirmation for each attended write stage.

## Limits requiring operator judgment

TWRP's CLI completion status does not reliably propagate all underlying wipe, formatting or ZIP installer failures. A shell exit code or `operation_end - status=0` is insufficient. Inspect fresh recovery logs and the actual target filesystem or installed image before proceeding. A timeout is an uncertain outcome; inspect current progress rather than automatically retrying a write. [Pinned recovery source](https://github.com/amazon-oss/android_bootable_recovery/tree/ebfcbc33edbc256c07e4f1e3657646d9dcdd7f01).

A TWRP backup staged under `/sdcard` consumes internal storage before off-device copying. NAS free space is not proof of sufficient internal space or decrypted/mounted Data. The raw route avoids that staging requirement but requires zero block-backed mounts and has a separate validation path. Raw images cannot be restored through TWRP's Restore UI.

The first backup occurs after the initial unlock. Neither backup route proves reversal of the boot-chain modification, captures RPMB, or provides a tested generic stock restoration recipe. Runtime package checks, synthetic regression tests and a successful TWRP boot do not establish later Android or HA acceptance.

The current test totals and observed hardware milestones are maintained in [validation status](preparation-status.md), rather than treating this review history as live installation state.

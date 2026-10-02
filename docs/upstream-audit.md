# Upstream package audit: Echo Show 5 (2021 / Gen2 / cronos)

Audit date: **2026-10-02 UTC**. Scope: download and inspect upstream files only. No downloaded programs, ADB/fastboot commands, NAS commands, or USB operations were executed.

## Current status: release acquired; source audit retained for reference

The initial download blocker described below was **resolved** by acquiring the genuine `amonet-cronos-v2.0.1.zip` through the normal browser download. Its contents and host runtime checks are documented in [release-audit.md](release-audit.md). Downloads and source snapshots are not published in Git; acquire and prepare the reviewed release using [the runbook](runbook.md). Source snapshots remain inspection material only.

### Initial download attempts (historical)

The author currently distributes **amonet-cronos-v2.0.1.zip** through [XDA attachment 6373838](https://xdaforums.com/attachments/amonet-cronos-v2-0-1-zip.6373838/), linked as the current release in the [author's unlock post](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-show-5-2nd-gen-2021-cronos.4772596/). The post was read successfully in Chrome; its last edit is 2026-09-11.

The archive download was not successful:

- A direct HTTPS request to the exact attachment returned HTTP 403.
- Clicking the author's actual attachment link in Chrome displayed `ERR_BLOCKED_BY_CLIENT` and a Chrome blocked-page screen. No browser protection was bypassed.
- No matching archive appeared in the local Downloads folder.
- Official GitHub API listings returned no releases in `R0rt1z2/amonet` and no amonet release in the inspected `amazon-oss/releases` listing. No maintainer-hosted replacement archive was established.

At that stage, the release contents and runtime were unverified, so `vendor/amonet/` and the unlock audit gate were deliberately absent. They were populated only after the later genuine release import and checks, not from the incomplete source snapshot.

The exact attachment was subsequently acquired through a normal browser download and inspected. No Dot, checkers, crown, or unofficial repack was substituted.

## Staged source snapshot: audit material only

The source linked by the current XDA post is [R0rt1z2/amonet, mt8163-echo-show](https://github.com/R0rt1z2/amonet/tree/mt8163-echo-show). Its resolved HEAD is **d6179b8a2ba45fb641acc38b1cf3e848e8ff235d**, commit timestamp **2026-08-15 23:35:34 UTC**.

Downloaded from [GitHub's commit-pinned archive endpoint](https://codeload.github.com/R0rt1z2/amonet/zip/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d):

- Local archive: `downloads/amonet-source-d6179b8a2ba45fb641acc38b1cf3e848e8ff235d.zip`.
- Size: **99,640 bytes**.
- Locally computed SHA256: **824ae9e9f5c6b485d55c5ba056d94fa65549b44860e9f78a33b495e3036a1c69**.
- Extracted source: `vendor/amonet-source/`, **62 regular files**. ZIP CRC passed. Absolute paths, parent traversal, and symlinks were rejected before extraction. Files were staged with data-only permissions; none were run.

This hash records the received GitHub source archive; it is not an independent publisher signature. There is no claim that this commit builds the exact released 2.0.1 archive.

### Why the source is not an installable fallback

[makedist.sh at the pinned commit](https://github.com/R0rt1z2/amonet/blob/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d/makedist.sh) still declares **VERSION=2.0.0**. The archive contains no `bin/` directory, no fastboot executable, no prebuilt fastbrick payload, and no TWRP image. It requires device-specific binary inputs absent from Git, including `preloader.img`, `lk.bin`, `tz.img`, `tee-payload.bin`, `cronos-kaeru.bin`, `twrp.img`, `fastbrick*.img`, and compiled BROM payloads.

Its submodules are references only, not downloaded content:

- `pl-payload`: [R0rt1z2/amonet-koboreru](https://github.com/R0rt1z2/amonet-koboreru), pinned **65120e2205c12b6c225533520a01c4cb9152cfec**.
- `idmetool`: [R0rt1z2/idmetool](https://github.com/R0rt1z2/idmetool), pinned **a18b85facd27392bdf9d5e3f1faeb410d609eaa4**.

Building missing components or assembling donor partitions would be a different, unvalidated route. It is not a safe way to fill the missing 2.0.1 package during preparation.

## Model identifiers: keep the namespaces separate

The pinned [README](https://github.com/R0rt1z2/amonet/blob/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d/README.md) maps:

- Echo Show 5 Gen2 / 2021: codename `cronos`, product **AEOCN**.
- Echo Show 5 Gen1 / 2019: codename `checkers`, product **AEOCH**.
- Echo Show 8 Gen1 / 2019: codename `crown`, product **AEOCW**.

The host `fastbrick.sh` and `fastbrick.ps1` instead contain a display-name dictionary with exactly **CRONOS**, **CHECKERS**, and **CROWN**. Neither dictionary contains AEOCN/AEOCH/AEOCW. This is a **label dictionary, not an allowlist**: the script accepts any nonempty `getvar product` value and prints an unknown-device label if it is absent from the dictionary. A BISCUIT/Dot response is therefore not rejected by the host-side identification step.

The package builder uses **DEVICE=cronos** and **DEVICE_TYPE_ID=A1XWJRHALS1REP** for Show 5 Gen2. The Python BROM path uses IDME `device_type_id`; the TWRP updater compares `ro.product.device` with `device.prop`'s lowercase `DEVICE`.

**Later physical probing observed `CRONOS` on a stock Gen2.** The wrapper recognizes `CRONOS` and `AEOCN` as source-supported candidates and rejects unrelated or unknown identifiers. The candidate mapping alone is insufficient to unlock: match the selected full physical serial, confirm the real package contents, and review discrepancies. Do not silently interpret a previously modified Gen2 reporting checkers as an ordinary stock target.

## Source-level behavior relevant to the future wrapper

Findings below describe the **pinned source**, not uninspected release binaries.

### Linux fastbrick and cronos profile

[fastbrick.sh](https://github.com/R0rt1z2/amonet/blob/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d/fastbrick.sh) loads `profile.sh` beside itself, then uses relative `bin/...` paths. It must be launched from the extracted `amonet/` directory. The [cronos profile](https://github.com/R0rt1z2/amonet/blob/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d/fastbrick/cronos/profile.sh) chooses only `bin/fastbrick.img`; its LK-specific image map is empty.

The script selects `bin/fastboot` whenever `uname -m` contains `64`, otherwise `bin/fastboot32`. This does **not** distinguish x86_64 from aarch64. The actual executable format must therefore be checked before any Synology use. The script needs Bash associative arrays, GNU-compatible `timeout`, and ordinary core utilities (`grep`, `cut`, `head`, `tr`, `sed`, `sleep`, `chmod`, `clear`; `tput` is optional for colors). A downloaded binary's shared-library requirements cannot be inferred from source. A Linux environment with matching architecture and libraries is required; DSM's bundled BusyBox tools are not automatically equivalent.

It queries `product`, `unlock_status`, and `lk_build_desc` using the selected executable **without `-s SERIAL`**. It does not enumerate or reject multiple devices. The first query can wait indefinitely. The `unlock_status` check only stops when the parsed value is `true`; an absent/unrecognized value is not treated as a hard failure. Passing arguments to the top-level shell script does not add serial targeting; they are unused.

After an interactive confirmation, the script calls `timeout 8 ... flash brick ...`. It checks output for eMMC permanent read-only and device-mismatch errors. Other outcomes retry every two seconds without a fixed attempt limit. Exit status **124** is interpreted as likely exploit success, but the script does not subsequently verify TWRP, model, serial, or a successfully unlocked bootloader. An interrupted USB transport is not proof of success. The payload's claimed model check cannot be independently audited from the absent binary.

### Other included source entry points

- `boot-recovery.sh` and `boot-fastboot.sh` invoke Python serial handshakes. The underlying `common.py` imports `pyserial` and can discover newly appearing serial ports. They are active mode-changing operations, not status probes; do not run them on a shared NAS during another device's conversion.
- `fastboot-step.sh` writes recovery and swdl, then reboots, using bare unqualified `fastboot` from PATH and no serial. It is not part of preparation and must never be invoked by an automatic health check.
- The source TWRP `update-binary` requires recovery mode and checks lowercase `ro.product.device == DEVICE`. It then writes critical bootloader components and recovery/swdl, clears MISC, and reboots. It is an updater for an existing unlock, not a read-only verification routine.
- No `backup.sh`, `backup.bat`, or restore scripts occur in this source snapshot. Older XDA quotations mention them, but the subsequent 2.0.1 release inspection also found none.

## Required safeguards for later execution

1. Fail closed while the genuine 2.0.1 archive is absent. Verify its ZIP CRC, safe paths, computed SHA256, expected model metadata/profile, required binaries/images, and binary architecture before enabling anything that writes.
2. Keep this Show project independent of the adjacent Dot project. Do not send ADB/fastboot/serial commands, restart their daemons, or change USB mappings while the Dot conversion is active. A separate output directory does not isolate a shared USB bus.
3. At the later bench session, require a selected full serial and exact model evidence, plus one exclusively assigned USB target. Reject BISCUIT, CHECKERS, CROWN, their product codes, empty identifiers, unknown devices, and ambiguity. Recheck immediately before any write. Do not rely on the upstream friendly-name dictionary as protection.
4. Any adapted wrapper must explicitly bind every operation to the reviewed target. Do not assume `ANDROID_SERIAL` is honored by the uninspected bundled binary, or that appending `-s` to the shell script changes its internal calls. Preserve the official package unmodified and document any wrapper adaptation separately.
5. Separate passive preparation, read-only inspection, unlock, backup, and OS installation into distinct stages. Do not pipe `YES` into an upstream script during preparation. Do not automatically retry an ambiguous write or change a payload to get past a model mismatch.
6. Maintain the Show's separate AC supply and stable data connection throughout unlock. The author's normal route uses a micro-USB data cable and all three buttons to enter stock FASTBOOT; no case opening, wire short, or special cable is specified.
7. Require observed TWRP and matching identity after unlock; never use exit 124 or a likely-success message as the acceptance criterion. Inspect current partition names, make a device-specific backup, copy it off the device, and verify integrity before any wipe. Backup data may include credentials and must remain private.
8. Install only the pinned cronos LineageOS ZIP via TWRP after backup. Avoid manual writes to Preloader/LK/TEE, blind slot assumptions borrowed from the Dot, generic restore scripts, or unreviewed relocking. The source's fallback recovery modes do not guarantee recovery from a damaged early boot chain.

## Release import requirements (subsequently completed)

The subsequent import checked the actual `amonet/device.prop`, profiles, launchers, executable file types, runtime dependencies and complete checksum inventory. It compared release scripts against the pinned source and retained the original release's differing Python modules. There are no backup/restore scripts in the release. See [the completed release audit](release-audit.md); no device was needed for these checks.

## Can the mt8163-cronos branch replace the release?

The [mt8163-cronos branch](https://github.com/R0rt1z2/amonet/tree/mt8163-cronos) was checked directly through the GitHub branch, commit and recursive tree APIs. It exists and identifies cronos correctly. Its HEAD is **0ce7c83d7fc98cac3eea245428df27b984151d6a**, dated **2025-12-22 14:22:54 UTC**, substantially earlier than the checked `mt8163-echo-show` HEAD from August 2026. It is not established as the source of the 2.0.1 release.

There are real build instructions for individual components: [lk-payload/Makefile](https://github.com/R0rt1z2/amonet/blob/0ce7c83d7fc98cac3eea245428df27b984151d6a/lk-payload/Makefile) and [microloader/Makefile](https://github.com/R0rt1z2/amonet/blob/0ce7c83d7fc98cac3eea245428df27b984151d6a/microloader/Makefile) use the `arm-none-eabi` GCC/binutils toolchain. These build component payloads; they do not generate a complete ready-to-use unlock package.

The [distribution script](https://github.com/R0rt1z2/amonet/blob/0ce7c83d7fc98cac3eea245428df27b984151d6a/makedist.sh) instead copies pre-existing inputs. The checked Git tree lacks:

- The entire `bin/` directory, including the expected `preloader.img`, `lk.bin`, `cronos-kaeru.bin`, `tz.img`, `twrp.img`, `microloader.bin` and GPT image.
- `brom-payload/` and its expected built payload.
- Referenced Python entry points `modules/load_payload.py` and `modules/main.py`.
- Referenced `bootrom-step.sh`, `fastboot-step.sh`, `gpt-fix.sh` and the optional fastbrick launchers/binaries.

There is no `.gitmodules` in this branch to supply those missing files automatically. Its `.gitignore` excludes `bin`, `build` and `dist/`. Merely cloning recursively, installing a compiler or downloading GitHub's source ZIP therefore does not supply the missing distribution inputs.

**Decision:** prefer the genuine compiled **amonet-cronos-v2.0.1.zip** for the documented conversion route. An independent source build is technically a separate engineering route: obtain matching firmware/recovery inputs, reconstruct the missing packaging dependencies, establish compatibility with the device's real bootloader, and validate the resulting complete package. That is considerably more work and uncertainty than acquiring the author's release. No local compilation was attempted, and no USB/device operation was run for this comparison. The conclusion is that this checkout is insufficient by itself, not that building any amonet component is impossible.

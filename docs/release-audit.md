# Release audit: amonet-cronos 2.0.1

Static audit date: **2026-10-02 UTC**. This audit inspected the genuine release ZIP as data. Later host runtime and physical-device checks are identified separately below.

## Result

The inspected **`amonet-cronos-v2.0.1.zip`** corresponds to [the author's XDA attachment 6373838](https://xdaforums.com/attachments/amonet-cronos-v2-0-1-zip.6373838/). Unlike the earlier GitHub source snapshot, this archive contains the cronos payload, TWRP image, host fastboot binaries, and model metadata needed for the documented route.

- Archive size: **44,403,627 bytes**.
- Locally recomputed SHA256: **07a49c8fb2b244330297810b261333ba23976eca5ab3e0d9032f45f4c9847621**.
- ZIP CRC: passed for every entry.
- Archive paths and symlink safety were checked before extraction.
- `amonet/device.prop` specifies **DEVICE=cronos** and **DEVICE_TYPE_ID=A1XWJRHALS1REP**, with the description Echo Show 5 (2021 / 2nd Gen).
- The cronos profile selects **`bin/fastbrick.img`** with an empty LK-specific image map.

This is a content/integrity audit of the supplied file, not an independent publisher signature or proof of reproducible compilation. It supersedes the earlier source audit's statement that the release was unavailable. The static review was followed by a successful NAS runtime check and later attended unlock/TWRP checks on physical hardware, recorded separately below.

## Actual contents and intended route

The ZIP has top-level `amonet/` and `META-INF/` directories. Its `amonet/bin/` contains:

- `fastbrick.img`: **114,294,812 bytes**, SHA256 **8217adc6d3dad0998e3685f0a692b37ff7dfeb1476ede8f732480c1e2a9dcb20**.
- `preloader.img`, `lk.bin`, `tz.img`, `tee-payload.bin`, and **`cronos-kaeru.bin`**.
- `twrp.img`: **15,910,912 bytes**, SHA256 **09a72dab093e9f4d444733bd4517af09444a0904a9a5243277df0ecd263873d8**.
- Linux `fastboot` and `fastboot32`, Windows `fastboot.exe`, `AdbWinApi.dll`, and `AdbWinUsbApi.dll`.

It also includes the shell/Windows fastbrick launchers, cronos profiles, Python serial/BROM modules, compiled BROM payloads, recovery-mode handshakes, and a TWRP update installer. **There is no ADB executable, backup.sh, backup.bat, restore script, boot-root.zip, or LineageOS ROM in this archive.** Backup, OS installation, and any required ADB tooling must therefore be handled separately.

For a stock Show 5 Gen2, the selected route remains the [author's fastbrick procedure](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-show-5-2nd-gen-2021-cronos.4772596/): Windows/Linux host, separate stock AC power, ordinary micro-USB data cable, all three physical buttons to stock FASTBOOT, then the cronos fastbrick flow. There is no need to build the GitHub source or run the BROM/serial recovery entry points during normal preparation. After verified TWRP and backup, install the separately pinned cronos LineageOS ROM through TWRP.

The TWRP `META-INF/com/google/android/update-binary` is the amonet updater for an already unlocked device. It validates `ro.product.device` against lowercase `cronos`, then writes early boot components and recovery/swdl, clears MISC, and reboots. It must not be mistaken for a harmless package-check command or manually run from Android/DSM.

## Exact comparison with the pinned source

Comparison base: `vendor/amonet-source/`, [upstream commit d6179b8a2ba45fb641acc38b1cf3e848e8ff235d](https://github.com/R0rt1z2/amonet/tree/d6179b8a2ba45fb641acc38b1cf3e848e8ff235d). Package profiles were compared with `fastbrick/cronos/profile.sh` and `.ps1` in that source.

**Byte-identical:** `fastbrick.sh`, `fastbrick.ps1`, `fastbrick.bat`, both cronos profiles, `bootrom-step.sh`, `fastboot-step.sh`, `boot-fastboot.sh`, `boot-recovery.sh`, `modules/gpt.py`, `modules/handshake.py`, `modules/handshake2.py`, `modules/load_payload.py`, `modules/logger.py`, the TWRP `update-binary`, and `updater-script`.

**Different:** `modules/common.py` and `modules/main.py`. The release uses the earlier single-block eMMC writing loop. The pinned source adds `BLOCKS_PER_WRITE=64`, a multi-block write protocol, an initial readback/fallback, and flushed progress output. This difference concerns the Python BROM/recovery path; the selected Linux fastbrick launcher is unchanged. **Do not copy the newer Python modules into the release package:** their matching payload protocol is not established by this audit.

The source builder's `VERSION=2.0.0` therefore must not be used to rename or reinterpret the actual supplied 2.0.1 release. Preserve and hash the release independently.

## Binary architecture and runtime requirements

ELF headers and dynamic sections were parsed from ZIP bytes without executing the programs:

- `bin/fastboot`: **ELF64, little-endian, x86_64 (machine 62)**. Interpreter: `/lib64/ld-linux-x86-64.so.2`. SHA256 **cb3d13b850143da85eb4b2099462514894459213da93d03d6ff4782d927d6e20**.
- `bin/fastboot32`: **ELF32, little-endian, i386 (machine 3)**. Interpreter: `/lib/ld-linux.so.2`. SHA256 **8912e9926cfc45503ad960866501305a684462b1dd1a44c5d82b1f075d6dd8c1**.
- Both list `libdl.so.2`, `libpthread.so.0`, `libm.so.6`, `librt.so.1`, `libgcc_s.so.1`, and `libc.so.6` as dynamic dependencies. Observed GLIBC version strings go through **GLIBC_2.15**. Symbol-version strings alone are not a successful loader test.
- `bin/fastboot.exe` SHA256: **b16950816e02f62c83e4725b9923b0087e3741e93635cc77facfd8a4fb621cd8**.

Neither Linux binary is an ARM64 build. The launcher's broad `uname -m` test chooses its 64-bit binary for any architecture containing `64`, so it is not a valid architecture check by itself. Synology's x86_64 environment passed the runtime check below. The stock macOS shell cannot execute these Linux ELF binaries directly.

### Completed NAS runtime and recovery-image checks

The actual bundled 64-bit fastboot was tested on a physical x86_64 Synology NAS. The container had **no USB mapping or network**, all capabilities dropped, no new privileges, a read-only root filesystem/package mount and an unprivileged user; only its temporary directory was writable. Each installation must repeat this validation against its own built image, recording the result privately.

- Every `ldd` dependency resolved.
- `fastboot --version` returned **28.0.0 rc1-eng.chaosm.20190910.064622** successfully.
- `bash -n` accepted the real `fastbrick.sh` and `profile.sh` without executing them.
- GNU `timeout` **9.1** and the `clear` utility were present.
- No `getvar`, device enumeration, handshake, unlock, flash or reboot command was run.

The TWRP boot image's LZMA ramdisk was decoded and its CPIO entries read as data. `prop.default` identifies **ro.product.device=cronos** and **armeabi-v7a**. Its fstab has single Boot/System/Data partitions, plus System Image, Cache, Persist, Misc, Recovery, LK and TEE entries; it does not use the Dot's A/B partition layout. These observations support the planned recovery identity and backup checks, but do not constitute a TWRP boot test.

`amonet-review.json` records SHA256 for all **31** regular files under `vendor/amonet/`. Per-host runtime validation is stored separately under ignored `private/`. The wrapper rejects missing, modified or extra package files, wrong model metadata, and an unvalidated or changed host image before unlock.

## Safety findings that remain true in the release

1. **Host identification is not a model allowlist.** Its `DEVICE_MAP` contains CRONOS, CHECKERS, and CROWN as friendly labels, but any nonempty product continues, including an unknown product. It relies on a later payload check. The inspected payload contains cronos/CRONOS and device-mismatch strings, but strings are not proof of correct control flow. The wrapper must reject unrelated or ambiguous devices before transmitting a payload.
2. **The launcher does not select a serial.** Internal fastboot calls have no `-s SERIAL`; arguments appended to `fastbrick.sh` are unused. Do not assume a shared NAS with another Echo attached is safe. Require physical/USB isolation or a reviewed wrapper that binds every command to the selected full serial and rechecks immediately before writing.
3. **Identifier namespaces differ.** Release metadata says `cronos` / `A1XWJRHALS1REP`; host labels use CRONOS. The upstream README additionally associates cronos with product AEOCN. The physical bench probe returned **CRONOS**. Both CRONOS and AEOCN have documentary association with Gen2, but neither should permit bypassing full identity/serial checks. Reject BISCUIT, CHECKERS, CROWN, AEOCH, AEOCW, blank values, and unknown identifiers.
4. **An eight-second timeout is only a likely-success signal.** The launcher treats exit 124 as likely exploit success and does not verify TWRP afterward. It retries other responses indefinitely, except explicit eMMC read-only and device-mismatch failures. Do not promote its exit code to a completed-conversion state.
5. **No safe dry-run is provided by upstream.** The launcher's preamble queries devices, then offers an interactive YES prompt. Keep it out of passive preparation and status checks. The serial handshake helpers also change device mode; `fastboot-step.sh` writes recovery/swdl using unqualified fastboot from PATH.
6. **Relative paths matter.** The launcher resolves its profile beside the script but uses relative `bin/` paths for tools and images. Execute it only from the correct extracted `amonet/` working directory, after checking the exact archive/manifest and wrapper gates.
7. **Keep the genuine release intact.** It contains no other model's named kaeru image. Do not add Dot binaries, substitute payloads, mutate model metadata, or merge source files to make a failed compatibility check pass.

## Completion boundaries

The actual release is structurally consistent with **cronos / Echo Show 5 Gen2**, and no host-script change was found that invalidates the earlier wrapper precautions. Device firmware compatibility still rests on the [author's 2026-09-11 explanation](https://xdaforums.com/posts/90734589/) of the current generic exploit; this offline audit did not establish a new firmware compatibility guarantee.

Release staging, content review and the NAS no-USB runtime test are complete. Serial/model/USB exclusivity gates remain in place.

### Subsequent physical bench evidence, 2026-10-02

A selected physical device reported stock product **CRONOS**, `unlock_status=false`, and LK **44072a3-20240709_162755**. The attended amonet 2.0.1 process exited **0**. Live recovery checks then established **ro.product.device=cronos**, **ro.build.product=cronos**, and **ro.twrp.version=3.7.0_9-0**. USB changed from **0bb4:0c01** to **18d1:4ee2**, retaining the same complete serial. These observations establish a successful TWRP boot on this unit and supplement the earlier offline image inspection.

The physical host also required selected-node access using temporary group read/write permissions with restoration of DSM's original **0600** mode, while retaining a nonroot container and a single USB-node mapping. Inherited Synology ACLs initially prevented ADB host-key setup; explicit **0700** permissions on `private/` and `private/adb-home/` resolved that without an administrator GID.

These later operations are distinct from static inspection. At the publication checkpoint, raw off-device capture passed length, device/NAS hash and GPT validation on the tested unit. The first Format Data stage was independently verified; the full wipe/install sequence is incomplete. No ROM installation, Companion installation or Android/HA acceptance is claimed. See [validation status](preparation-status.md). The host exit code alone is still insufficient evidence for any future unlock; retain the independent identity and TWRP checks.

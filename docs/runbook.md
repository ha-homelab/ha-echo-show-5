# Installation runbook

Target: **Echo Show 5 Gen2 / 2021 / cronos** only. USB host: a physical **x86_64 Synology NAS** with Docker and Python 3.8 or newer. Run these stages deliberately, one at a time.

## 0. Prepare a fresh checkout

Start with a checkout on the workstation:

```bash
git clone https://github.com/ha-homelab/ha-echo-show-5.git
cd ha-echo-show-5
```

Run workstation commands from this repository root. The Linux tools execute on the NAS through SSH; they do not run directly on macOS. Configure your own host and destination:

```bash
export SHOW5_SSH_HOST=YOUR_NAS_SSH_ALIAS
export SHOW5_REMOTE_ROOT=/volume1/docker/ha-echo-show-5
```

Replace `YOUR_NAS_SSH_ALIAS` with an SSH configuration alias or `user@host`. The defaults are `synology` and `/volume1/docker/ha-echo-show-5`. The destination must be an absolute simple path without spaces or traversal components. The SSH user must be able to run the configured Docker binary and narrowly scoped USB permission commands through noninteractive `sudo`; configure this according to your NAS administration policy.

Download the pinned ROM and APK:

```bash
python3 scripts/artifacts.py fetch lineage companion
python3 scripts/artifacts.py verify lineage companion
```

Acquire the genuine **amonet-cronos-v2.0.1.zip** from [the author's attachment](https://xdaforums.com/attachments/amonet-cronos-v2-0-1-zip.6373838/). The downloader can try the same URL:

```bash
python3 scripts/artifacts.py fetch amonet
```

If XDA blocks automated download, download the original attachment through your browser and place the file at `downloads/amonet-cronos-v2.0.1.zip`. Do not substitute another model's archive, an unofficial repack, or GitHub's source ZIP. The expected size is **44,403,627 bytes** and the recorded SHA256 is **`07a49c8fb2b244330297810b261333ba23976eca5ab3e0d9032f45f4c9847621`**. This amonet digest records inspected bytes, not an independently published signature.

```bash
python3 scripts/artifacts.py verify amonet
python3 scripts/prepare_amonet.py
python3 -m unittest discover -s tests -v
python3 scripts/remote.py sync
python3 scripts/remote.py prepare-host
python3 scripts/remote.py preflight
```

`prepare_amonet.py` verifies and extracts the reviewed package without executing it. The public audit records all **31** extracted file hashes. `prepare-host` builds the dedicated container and invokes the separate release-tool validation without USB access. Local host-image and runtime-validation records belong under NAS `private/`. Rebuilding an image requires revalidation; a published image ID from another machine is not proof of local validation.

The sync excludes NAS backups, logs, keys and Git metadata and does not use `--delete`. Downloaded artifacts and extracted packages are copied for execution but remain ignored by Git. Preparation does not unlock a device.

If already logged into the NAS, run `python3 scripts/nas.py ACTION ...` from the configured project directory instead of using `remote.py`. See [release audit](release-audit.md) for package findings and [validation status](preparation-status.md) for the latest physical checkpoint.

### Boundaries

- The initial unlock changes the boot chain. This route does not provide an untouched-stock backup before unlock.
- The first backup is made in TWRP **after unlock and before formatting**. Raw capture covers the eMMC user area and both boot areas, excluding RPMB. The alternative TWRP Boot/System/Data backup excludes internal shared storage. Neither is a tested generic stock-restore procedure.
- LineageOS replaces Fire OS and Alexa and requires data formatting. Its limitations are in [the HA guide](android-and-home-assistant.md).
- Keep AC power, USB and device selection stable during writes. A timeout or “likely successful” message is not proof that a stage completed.
- If a unit is already in verified TWRP, continue at the backup stage; do not repeat unlock simply to follow this document from the beginning.

## 1. Connect and identify the exact Show

Finish any other Echo conversion using this NAS before beginning. The scripts refuse USB stages while matching Echo conversion containers are running. Inspect a leftover container with its owner; do not blindly stop it, kill another project's ADB server or change unrelated USB mappings.

Connect the Show's **normal AC adapter** and a **micro-USB data cable** to the NAS. USB does not replace the normal power supply. The author's ordinary route does not require opening the enclosure, soldering or a special cable.

```bash
python3 scripts/remote.py inventory
```

Inventory reads Linux sysfs without opening a USB device. Identify the physical port and complete serial of the intended Show. Ignore unrelated NAS devices even if they use an Amazon, MediaTek or Google USB vendor ID.

For stock **FASTBOOT**, power the Show off, hold **Volume Down + Volume Up + Mute**, apply power and keep holding until FASTBOOT appears. This differs from the Echo Dot procedure. [Author's unlock instructions](https://xdaforums.com/t/unlock-root-twrp-unbrick-amazon-echo-show-5-2nd-gen-2021-cronos.4772596/).

```bash
python3 scripts/remote.py inventory
python3 scripts/remote.py probe-fastboot --port PORT --serial FULL_SERIAL
```

`PORT` and `FULL_SERIAL` are placeholders for your observed values. The wrapper recognizes **CRONOS** and the upstream-documented **AEOCN** as cronos candidates and rejects unrelated or ambiguous products. Read the raw product, full serial and locked-state evidence before continuing. A USB serial during a transient preloader mode may differ from the stock device serial and is not sufficient identification by itself.

Each container receives only the selected `/dev/bus/usb/BBB/DDD` node, with no host network, all capabilities dropped and no privileged-container flag. The wrapper rechecks the node before every command. DSM nodes may start at mode `0600`; the wrapper temporarily grants the node's existing group read/write access and restores its original mode when the same node remains present. Private ADB directories use explicit `0700` permissions to address inherited DSM ACLs. These adjustments do not expose the whole USB bus.

## 2. Confirm the unlock package and host audit

Before an unlock, `preflight` must report the genuine release and its locally validated host as ready. Review [the actual release audit](release-audit.md), particularly its unqualified upstream fastboot calls and the wrapper's single-node isolation.

The gate checks the archive size/hash/CRC, safe extraction, exact reviewed file set, model metadata and local host runtime validation. The package's `device.prop` must identify `cronos` and `A1XWJRHALS1REP`. Its profile selects `bin/fastbrick.img`. The exploit requires the modified bundled x86_64 fastboot; the standard diagnostic fastboot is not a replacement.

Do not regenerate audit hashes to accept an unexpected file. Do not merge newer source modules into the release, rename another device's images or fill missing files with unrelated binaries. A future upstream release requires a new review.

## 3. Unlock and independently verify TWRP

Only for an untouched unit with a successful stock FASTBOOT probe:

```bash
python3 scripts/remote.py unlock --port PORT --serial FULL_SERIAL
```

Enter `UNLOCK FULL_SERIAL` for the actual selected serial, then follow the author's prompts. The wrapper checks package integrity, selected identity, product and locked status before invoking the original release from its proper working directory.

Leave power and data connected while the original process runs. The upstream launcher interprets one timeout as likely exploit success; the project requires a separate recovery check. After USB re-enumeration:

```bash
python3 scripts/remote.py inventory
python3 scripts/remote.py probe-recovery --port PORT --serial FULL_SERIAL
```

The probe requires cronos identity and a TWRP version. If the complete serial changes between modes, establish the physical port transition and confirm the same device before selecting its new observed serial. Never reuse a stale USB-node mapping or automatically retry fastbrick after an uncertain result.

The project has observed **TWRP 3.7.0_9-0** on physical cronos hardware. This is evidence for the unlock checkpoint, not Android or HA completion.

### TWRP CLI readiness and results

A combined read-only CLI query stalled during the first recovery GUI transition in the test session; a later single bounded query completed normally. The exact cause was not proven. If a read-only query stalls, inspect processes and `/tmp/recovery.log` through ordinary ADB shell commands before retrying. Do not read, delete or recreate the CLI FIFOs, and do not restart unlock merely because a CLI client stalls. Use one CLI command per invocation.

The [pinned recovery source](https://github.com/amazon-oss/android_bootable_recovery/tree/ebfcbc33edbc256c07e4f1e3657646d9dcdd7f01) does not propagate every underlying operation failure through the CLI result. **Exit zero, `operation_end - status=0`, `Install took ...` and `Done processing script file` are not sufficient proof of a successful write.** Review fresh operation logs, the expected target and the resulting filesystem or installed image. For ZIP installation, verify successful updater termination. A timeout is an uncertain outcome, not a reason to retry a write automatically.

## 4. Make and verify the first backup

Do not format Data or wipe System before a verified off-device backup exists. Inspect the actual recovery partition map, Data mountability/encryption state, internal free space and NAS capacity. `/sdcard` existing as a directory is not proof that Data is mounted or decrypted.

### Raw eMMC capture directly to the NAS

Use the raw route when the internal filesystem lacks enough space for a staged TWRP backup or when preserving the post-unlock eMMC state is desired. In the verified recovery session, unmount all block-backed filesystems first. Inspect the actual mount list; the script deliberately refuses to capture while any block-backed mount remains. Do not remount storage or run TWRP CLI probes during capture.

```bash
python3 scripts/remote.py backup-raw --port PORT --serial FULL_SERIAL
python3 scripts/remote.py verify-backup --serial FULL_SERIAL
```

The capture requires `BACKUP-RAW FULL_SERIAL`. It streams binary data directly to NAS through ADB shell-v2 with `-T`, keeping stderr separate. It checks actual block-device sizes, exact captured lengths, device/NAS SHA256 values, both GPT CRCs, partition bounds and the observed partition mapping. Do not substitute text-decoding shell output for this binary path.

The private manifest is `backups/FULL_SERIAL/raw-TIMESTAMP/raw-backup.json`. `verify-backup` has a separate raw-image validation path when a TWRP-format backup is absent. A partial image or a running process does not satisfy the gate.

This captures the eMMC user area plus `boot0` and `boot1` **after unlock** and excludes RPMB. It does not prove stock restoration. **Never select a raw image in TWRP's Restore UI.** Raw restoration would need a separately reviewed procedure based on that device's verified partition map; no generic raw restore is supplied.

### Alternative TWRP Boot/System/Data backup

If Data is mounted/decrypted and internal capacity permits, the `backup` action uses `twrp backup BSD`. It requires fresh completion evidence, copies files to NAS `backups/FULL_SERIAL/TIMESTAMP/files/`, compares device and host size/hash, and validates boot-image and archive structure. It excludes internal shared storage. [TWRP command-line reference](https://twrp.me/faq/openrecoveryscript.html).

```bash
python3 scripts/remote.py backup --port PORT --serial FULL_SERIAL
python3 scripts/remote.py verify-backup --serial FULL_SERIAL
```

Do not wipe encrypted or unmountable Data merely to make backup creation work. Resolve preservation first.

### Keep a second private copy

After verification, copy the backup to another private location. For the configured SSH destination:

```bash
mkdir -p backups
chmod 700 backups
rsync -rt "${SHOW5_SSH_HOST:-synology}:${SHOW5_REMOTE_ROOT:-/volume1/docker/ha-echo-show-5}/backups/" backups/
```

Retain the manifests and logs alongside the images. Backups and ADB authorization keys must never be committed or published.

## 5. Install LineageOS through TWRP

The pinned ROM is **lineage-18.1-20260904-UNOFFICIAL-cronos.zip**, release **lineage-18.1-cronos-v0.4**. The downloader checks its published SHA256, archive CRC and `pre-device=cronos`. [Release](https://github.com/amazon-oss/releases/releases/tag/lineage-18.1-cronos-v0.4), [author's installation instructions](https://xdaforums.com/t/rom-unofficial-11-cronos-lineageos-18-1-for-the-amazon-echo-show-5-2021.4772598/).

Proceed only after the off-device backup passes verification and its documented scope is understood. Follow the author's sequence: **Format Data → wipe Data/System/Cache → install ROM → Format Data again → reboot System**.

Use either TWRP's attended UI controls or the guarded CLI stages below. Do not perform both as duplicate sequences. Run and inspect **one stage at a time**; the displayed command blocks are references, not unattended batch scripts.

First use **Wipe → Format Data** in the UI, or:

```bash
python3 scripts/remote.py format-data --port PORT --serial FULL_SERIAL
```

Then use **Advanced Wipe → Data, System, Cache**, or the following individual stages, reviewing each result before starting the next:

```bash
python3 scripts/remote.py wipe-data --port PORT --serial FULL_SERIAL
python3 scripts/remote.py wipe-system --port PORT --serial FULL_SERIAL
python3 scripts/remote.py wipe-cache --port PORT --serial FULL_SERIAL
```

Do not select unrelated bootloader partitions. Each guarded stage revalidates TWRP identity and the saved backup, requires the exact action/serial phrase and retains before/after recovery evidence under private `logs/FULL_SERIAL/TIMESTAMP-operation/`. CLI completion alone does not establish success.

Transfer and rehash the ROM, then begin its separate installation stage:

```bash
python3 scripts/remote.py stage-rom --port PORT --serial FULL_SERIAL
python3 scripts/remote.py install-rom --port PORT --serial FULL_SERIAL
```

Inspect the new installation log and installed image. Only after successful installation, **Format Data again** through the UI or the guarded `format-data` command. Then choose **Reboot → System**. Installation does not automatically format or reboot. Allow first boot to finish, join Wi-Fi and verify the installed OS and basic touch/audio operation.

GApps and root packages are unnecessary for the pinned minimal Companion APK. Do not manually flash Preloader, LK, TEE or an Amazon update through stock fastboot.

## 6. Install Companion and complete HA acceptance

Enable Android Developer options and USB debugging, then authorize this project's NAS ADB key on the Show. The key persists under NAS `private/adb-home/`. Rerun inventory if the serial or USB node changes.

```bash
python3 scripts/remote.py probe-android --port PORT --serial FULL_SERIAL
python3 scripts/remote.py install-companion --port PORT --serial FULL_SERIAL
```

The installer requires cronos, Android 11, LineageOS 18.1 and completed boot. Complete login and the display/audio/network checks in [the HA guide](android-and-home-assistant.md). Disable USB debugging when it is no longer needed; the app operates over Wi-Fi.

## Recovery and failure handling

- Before any write, correct package, selection or host failures using the diagnostic. Preflight, inventory and probes do not write firmware.
- After unexpected write output or a disconnect, preserve logs and current device state. Do not substitute another model's image or repeatedly rerun the exploit.
- A verified **TWRP-format** backup may be copied back with its original `files/<TWRP-device-folder>/<backup-name>/` structure and restored through the corresponding UI after checking device identity and partition layout. This does not apply to raw images.
- No generic restore, relock or stock-image script is supplied. Early boot-chain damage may not be recoverable through the ordinary USB route; a post-unlock backup does not promise to undo the initial unlock.

Keep actual device identifiers, network configuration and detailed bench outcomes in ignored local records. Publish only sanitized milestone summaries with their verification limits.

# Remote access and local automation on the installed Android build

Research checked **2026-10-29**. Scope: the already converted **Echo Show 5 Gen2 / cronos**, running the project's **LineageOS 18.1 / Android 11** port. This is an expansion plan, not a record of enabling new services. The [Android runbook](android-and-home-assistant.md#persistent-wi-fi-adb-on-the-tested-rom) records the existing ADB installation and its recovery limits; a candidate below is not installed or accepted merely because upstream supports Android 11.

The most useful combination is the existing HA control path, host-side screen control when needed, and a carefully selected SSH route. The live inventory found **`/system/bin/ssh` and `/system/bin/sshd` on both Shows**: assess those existing binaries before installing a second server. No Termux or Termux:API package was installed at this checkpoint. Opening more ports does not add sensor drivers, grant Android system privileges or solve microphone ownership.

## Choose the interface for the job

| Interface | Useful work | Authority and current status |
| --- | --- | --- |
| Existing HA and VACA controls | Normal room operation, screen/media actions, status, voice and selected app launches | Existing project route; capabilities depend on the installed app and integration |
| Existing authenticated ADB | Package inventory, app deployment, selected settings, diagnostics, recovery and explicit app launches | Verified Android **shell UID 2000**, not root |
| Bundled OpenSSH client/server | Potential encrypted terminal and file-transfer route without another APK | Both binaries observed; listener, login identity, authentication and startup are not yet accepted |
| scrcpy on a trusted computer | See and operate the small screen remotely; fix a setting without walking to the Show | Candidate using authorized ADB; no permanent remote-desktop app required |
| Termux plus OpenSSH/SFTP | Maintain app-owned scripts/files, run bounded local jobs and transfer their outputs | Candidate, Android app UID; not equivalent to ADB or a system SSH login |
| Termux:Boot / Tasker / explicit app intents | Start selected user-space helpers and perform local workflows | Candidate; permission, startup and resource behavior require acceptance |
| Telnet server | Another terminal transport | No recommended role: adds a listener without expanding Android authority |

Keep routine HA actions in the existing fixed command mapping. Its named camera, player and call actions already provide clearer behavior than a general remote shell. See [remote endpoint controls](remote-endpoint.md).

## ADB: preserve the working route and distinguish authentication from encryption

The installed ROM's boot configuration already starts the TCP ADB listener. Previous device checks recorded host-key authentication and UID 2000, including return after a normal reboot. Those observations do not establish recovery after every Wi-Fi outage or power loss. The runbook also records a screen-off Wi-Fi reconnection limitation. Adding SSH cannot restore a missing Wi-Fi route.

**The existing legacy TCP5555 transport is not Android 11's paired TLS wireless-debugging transport.** AOSP documents legacy TCP ADB as unencrypted even after the host's key is authorized. The newer wireless-debugging flow uses TLS and a separately selected port. `ro.adb.secure=1` is therefore evidence of ADB authorization, not transport encryption. [AOSP ADB Wi-Fi architecture](https://android.googlesource.com/platform/packages/modules/adb/+/HEAD/docs/dev/adb_wifi.md)

Use the existing management network and trusted host. For access from outside the home, reach that management network through the existing VPN or trusted administration host; do not publish the Show's ADB listener. An SSH connection to a nearby administration host protects the remote leg, but the remaining host-to-Show legacy ADB leg is still the local network's responsibility.

Android 11 generally supports pairing-based wireless debugging, but this unofficial ROM's Settings UI, daemon build, discovery and reboot behavior must be checked before choosing it. A migration would also need to update the existing HA ADB integration: a fixed legacy port must not be silently replaced with an assumed TLS endpoint. Keep the currently working recovery path until the replacement is verified. [Official Android ADB guide](https://developer.android.com/tools/adb#connect-to-a-device-over-wi-fi-android-11+)

## Remote screen control: the next small, useful addition

Use **scrcpy from the trusted administration computer** for interactive maintenance. Upstream supports display/control from Android 5 onward, over USB or TCP/IP, without root. This makes Android 11 a supported platform candidate; it does not prove this vendor encoder works correctly. Direct camera mirroring requires Android 12, so that feature is not an option for this installed ROM. [Official scrcpy project](https://github.com/Genymobile/scrcpy)

Start acceptance with a modest frame rate and **audio disabled**. Audio forwarding is on by default upstream, and Android 11 has an additional unlocked-screen requirement. It can also change where sound plays. There is no reason for a settings session to acquire or reroute audio while VACA or a call is active. [scrcpy audio behavior](https://github.com/Genymobile/scrcpy/blob/master/doc/audio.md)

After verifying the intended device against the private inventory, a maintenance session can use an existing authorized ADB target:

```sh
scrcpy --serial "$ADB_TARGET" --no-audio --max-size=960 --max-fps=15
```

`ADB_TARGET` is the exact selected ADB target, not a wildcard or an automatically chosen first device. Record screen-control success, orientation, encoder stability, VACA continuity and return to the clock. Do not record the session or mirror the camera as part of this acceptance. Closing scrcpy is the normal rollback; it does not require changing the default Home app or leaving an always-on desktop server.

## Bundled OpenSSH: inspect before adding another server

The October 29 follow-up observed `ssh -V` reporting **OpenSSH 8.3p1,
BoringSSL** on both devices. `/system/etc/ssh/sshd_config` exists and disables
password authentication, with host and authorized-key paths under `/data/ssh`.
The directory has owner/group `root:shell` and mode `0750`. No `sshd` process,
TCP22 listener, or SSH declaration in the inspected system/vendor init files
was observed. Private host keys were not read. These findings establish an
installed candidate, not a tested login, server binary identity or boot service.
The legacy ADB connection remains active; `adb_wifi_enabled=0` and the paired
TLS properties were empty at this checkpoint. Full facts are in the
[installed capability audit](installed-capabilities.md).

The binary inventory changes the implementation order. First determine whether the ROM's existing SSH server can provide a maintained, narrowly scoped management channel. **A server binary on disk does not establish a running listener or a usable authenticated login.** Likewise, a binary under `/system/bin` does not itself mean the process or resulting session runs as root.

LineageOS 18.1's common product configuration includes `ssh`, `sshd`, `scp`, `sftp`, the server configuration, `ssh-keygen` and `start-ssh`. Its `lineage-ssh.rc` creates SSH data directories after the data filesystem becomes available; that file does **not** declare or start an SSH daemon. This supports the observed presence, but is not proof of this unofficial device build's complete init configuration. [Lineage package selection](https://github.com/LineageOS/android_vendor_lineage/blob/lineage-18.1/config/common.mk), [Lineage SSH directory setup](https://github.com/LineageOS/android_vendor_lineage/blob/lineage-18.1/prebuilt/common/etc/init/lineage-ssh.rc)

The inspected upstream OpenSSH branch declares version **8.3p1**. Its Android configuration disables password authentication and names host/authorized-key files under `/data/ssh`. The launcher selects `/vendor/etc/ssh/sshd_config` and keeps the process in the foreground for supervision. These are source observations, not verified values of the installed server. In particular, compare the actual configuration location with the launcher before assuming that they form a working pair. Do not copy the upstream launcher's historical key-generation choices into a new deployment. [Pinned version definition](https://github.com/LineageOS/android_external_openssh/blob/6160989a0f1b8f9650b699fddfb4df3f6cf15677/version.h), [Android configuration](https://github.com/LineageOS/android_external_openssh/blob/6160989a0f1b8f9650b699fddfb4df3f6cf15677/sshd_config.android), [launcher](https://github.com/LineageOS/android_external_openssh/blob/6160989a0f1b8f9650b699fddfb4df3f6cf15677/start-ssh)

Complete the read-only assessment before choosing a server:

- Record the installed binary version, actual server configuration, configuration includes and relevant init service definitions. A client version alone does not prove server build identity.
- Determine whether a listener/process exists, its bind addresses, its UID and its startup owner. Do not infer a running service from a directory or a script.
- Inspect host-key and authorized-key **paths, ownership and permissions**, without exporting private keys. Record which account and file tree a prospective login would expose.
- Check whether SFTP is actually configured and which installed implementation it uses. An `sftp` client binary does not prove that the server subsystem works.
- Review maintenance of the bundled version and its dependencies before exposing it beyond a controlled test. A newer ROM packaging date or `userdebug` label does not establish that its SSH package received current fixes.

The live build reports Android 11/API 30, `userdebug`, `ro.debuggable=1`, a `2024-02-05` security patch level, and permissive SELinux. Those facts warrant a limited management boundary; **they do not grant every Android app root access**, remove ordinary file ownership checks, or prove a supported privileged SSH deployment. The actual ADB session remains UID 2000. The goal is a defined authenticated management channel, not a change to the ROM's privilege policy.

If the built-in daemon cannot meet the required account scope, maintenance and startup contract, use the app-owned alternative below. There is no daemon-enabling, root-login or init-modification procedure in this assessment.

## Termux SSH and SFTP: an app-owned alternative

**Termux plus its OpenSSH package is a reasonable optional local tool environment.** Upstream supports Android 7 and later; the official `v0.118.3` release includes an `armeabi-v7a` asset, matching the installed ROM's 32-bit application ABI. Select and verify a maintained compatible release when implementing the pilot rather than treating that observed release as a permanent version recommendation. Termux and every plugin must come from the same signing source. Its F-Droid and GitHub distributions are not interchangeable in place. [Termux installation documentation](https://github.com/termux/termux-app#installation), [observed official release](https://github.com/termux/termux-app/releases/tag/v0.118.3)

OpenSSH provides encrypted shell sessions and file transfer. The Termux package includes SFTP support and its configuration is under the Termux prefix; its packaged configuration documents port **8022**, not the system SSH port. Read the installed effective configuration instead of assuming a listener or default authentication policy exists. [OpenSSH project](https://www.openssh.org/), [Termux OpenSSH package](https://github.com/termux/termux-packages/blob/master/packages/openssh/build.sh), [Termux server configuration patch](https://github.com/termux/termux-packages/blob/master/packages/openssh/sshd_config.patch)

The important boundary is the Unix identity. Termux processes, including SSH sessions, run as the Termux Android app. They can manage that app's private files and storage deliberately granted to it. They do not acquire shell UID 2000, read another app's private data, install system services or obtain privileged Android permissions. A Linux-looking directory tree or a `proot` environment does not change this boundary. Likewise, ADB's `run-as` only works for packages that permit that debugging operation; it is not a general route into all app data. Android applies its app UID sandbox to native programs too. [Android application sandbox](https://source.android.com/docs/security/app-sandbox)

Good local workloads include a small queue of approved tasks, a diagnostic heartbeat, rotation of that helper's own logs, downloading an approved offline asset and reporting its checksum, or serving a local-only status page for its own state. Keep video transcoding, speech models, long compilation jobs and the main HA service on the existing servers. Those workloads compete directly with the Show's foreground display and real-time audio.

An SSH pilot should have a specific owner and purpose:

1. Record the selected APK/package versions and verify the ABI and signing source before installation. Do not replace an existing Termux installation without first preserving its app data.
2. Create a device-specific SSH host key and a dedicated administrator key. Verify the host fingerprint through the already trusted channel. Keep key material outside Git.
3. Limit reachability to the management path and validate key login. Disable password/interactive authentication when that key path works; do not rely on the port number as access control. Avoid agent forwarding and extra forwarding features unless the selected workflow needs them. [OpenSSH server options](https://man.openbsd.org/sshd_config)
4. Test an interactive, bounded session first. Confirm the resulting UID and accessible directories, then transfer and remove a harmless file in the helper's own directory.
5. Add boot startup only if there is a continuing local job. Verify a normal reboot, Wi-Fi recovery, CPU/RAM use, log limits and unchanged voice/call behavior. A boot entry alone proves none of these.

For rollback, stop the owned SSH service, remove its own boot entry and revoke its administrator key/network allowance. Export any needed app-owned files before uninstalling. Preserve the existing ADB and VACA configuration.

## Boot helpers and automation

**Termux:Boot** can start selected Termux scripts after boot. Its documented setup requires opening the plugin once, and its signature must match Termux. **termux-services** can supervise those services. Use one owner for each helper; do not simultaneously launch the same daemon from Boot, a shell profile, Tasker and a supervisor. Apply log rotation and restart backoff so a broken helper cannot become a tight restart loop. [Termux:Boot](https://github.com/termux/termux-boot), [termux-services](https://github.com/termux/termux-services)

Do not copy a permanent wake lock into every startup script. First measure whether the helper needs one and whether it changes the established screen and Wi-Fi behavior. Android background limits still matter to third-party apps; this port's disabled deep sleep does not establish that every app can run indefinitely. [Android background power behavior](https://developer.android.com/training/monitoring-device-state/doze-standby)

**Tasker is optional**, not a prerequisite for HA automation. Its Termux plugin can run local helper scripts, but it does not make a normal app's shell privileged. Termux also exposes a permission-controlled `RUN_COMMAND` integration; enabling external execution is a deliberate additional interface, not something needed for SSH. Prefer a few reviewed tasks with bounded arguments and timeouts over accepting arbitrary command strings from a dashboard or webhook. [Termux:Tasker](https://github.com/termux/termux-tasker), [Termux command interface](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent), [Tasker shell action](https://tasker.joaoapps.com/userguide/en/help/ah_run_shell.html)

**Explicit intents and app links** are often enough for launching a player, opening a fixed meeting room or returning to the clock. An intent asks an app to perform an exposed action; it cannot manufacture an action that the receiving app does not implement. Keep installed package names, allowed actions and URI schemes in the private endpoint mapping, and verify the target package/version. Android 10 and later restrict background activity launches, so a successful manual tap is not proof of unattended background launch. [Android common intents](https://developer.android.com/guide/components/intents-common), [background activity launch rules](https://developer.android.com/guide/components/activities/secure-bal)

The most valuable future extension is a single local action broker that owns foreground app changes and audio/camera leases, reports completion to HA, and returns to the clock. It should expose named operations such as `open_player` or `return_home`, not a network shell. That is proposed application work. Installing SSH, Tasker or a launcher does not implement the broker or make unrelated apps participate in the current SIP/VACA microphone lease.

## Why Telnet is not in the recommended plan

The useful part of a terminal is the process it can run and the identity it runs as. Telnet would not raise that identity or expose additional hardware. A plain Telnet service also lacks the encrypted authenticated transport already supplied by SSH. It would duplicate terminal access while adding another service to maintain. Use SSH/SFTP for the optional app-owned Unix environment, and authorized ADB for Android administration. There is no Telnet installation or listener-enabling procedure in this plan.

The acceptance result for this document is **research complete, bundled SSH binaries found, no new access service deployed**. Existing ADB behavior remains the dated observation in the Android runbook. Neither the bundled SSH server nor an optional replacement is described as operational until its authentication, identity, transport and recovery tests pass.

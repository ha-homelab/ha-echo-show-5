# OTT command-server connection

The Show runs our `play.ott.foss` Capacitor application. Its historical Android
source predates the current OTT command-server client, so the local Show build
adds the acknowledged outbound transport and a compatibility adapter for the
existing player. Apply the remote-control patch after the startup/poster patch;
see [the build procedure](remote-endpoint.md#reproduce-the-local-build-and-installation).

The connection uses the existing private control-server address and a separate
access code for this installation. It makes outbound authenticated requests;
the Show's local HTTP listener stays disabled. The administrator credential
belongs only in the operator's local CLI/server configuration, never in the app.

## Local CLI alias

The operator alias is `s2`. Registration uses the app's existing device UUID:

```bash
ott add s2 DEVICE_UUID
```

Use the existing CLI configuration at `~/.config/ottplay-control/cli.json`; do
not create a parallel database or replace other aliases. `ott add` provisions
the configured server and stores the alias with owner-only permissions. Do not
put the actual UUID, server configuration or access code in this repository.
`ott pair s2` displays the private connection settings; do not paste its output
into public logs or tickets.

Open **OTTPlay FOSS** from the Show's HA dashboard, then open **Settings → Remote
control → Command server**. Enter the existing **HTTPS** server address and this
device's access code, and connect. Use the final URL with a trusted certificate;
HTTP addresses and redirects are rejected before forwarding credentials. A bare
hostname from an older configuration must be replaced by its explicit HTTPS URL. The saved connection resumes when the
application starts. Disconnect from that same page to stop polling.

## Available commands

The legacy compatibility adapter supports live status, channel listing/search,
channel selection, volume, notifications and provider listing:

```bash
ott s2
ott s2 s
ott s2 s "channel name"
ott s2 play "exact channel name"
ott s2 v
ott s2 v 35
ott s2 providers
ott s2 msg "Remote control ready"
```

The newer CLI also advertises provider/profile edits, Plex setup, EPG/archive
search, VPortal, kiosk policy and additional restart controls. Those need player
support that this compatibility adapter does not provide; unsupported actions
return an explicit response. Do not treat a server acknowledgement as proof of
video decoding or audible output.

## Connection lifetime and private settings

Remote commands work while the OTT application is running. The HA **Home/Stop**
action intentionally closes OTT and restores the clock, so the command server
cannot answer on its behalf afterward. Open OTTPlay FOSS from HA before using
the CLI. This connection does not provide an Android app launcher.

Connection credentials stay local to the installation and are excluded from
settings exports. Importing settings revokes active connection consent. Server
address, token and enablement must not be imported from another player. Keep
APK signing keys, filled mappings, downloaded packages and live test evidence
under the ignored private/download directories.

## Verified on the second Show

On October 4, 2026, the signed `1.1.42-show5.2` / `10144` upgrade preserved the
installation UUID, M3U configuration and HLS.js preference. Native outbound
polling connected while the local HTTP listener remained disabled. The existing
16 local aliases were preserved; the CLI and credential files retain mode `600`.

The real CLI returned live status in 1.16 seconds. Channel search, provider
listing, numeric channel selection and volume set/readback succeeded. Playback
decoded 199 additional 1920×1080 frames over eight seconds without a media error.
A profiles request returned an explicit unsupported response in 1.6 seconds.
After HA Home closed the process, launching OTT again restored the connection
without re-entering credentials; CLI status returned in 1.98 seconds. These are
individual observations, not a latency guarantee or a network-loss soak test.

The source checks cover command acknowledgement/retry/cancellation, private
settings export/import, legacy action responses, startup, playback and Android
policy. Both original patches applied cleanly to a fresh archive of the pinned
source; their resulting files matched that signed build. Signing and the Full
distribution audit passed. Physical audibility and Android reboot recovery were
not part of this check.

The patch now also requires HTTPS and disables redirects in browser and native
transports. This later hardening was verified against the pinned source with
synthetic tests; it is not included in the historical APK described above. No
new APK or device installation is claimed. Rebuilding requires a new version
code/name and the existing local signing identity before installation.

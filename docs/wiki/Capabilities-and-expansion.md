# Capabilities and expansion

[Wiki home](Home.md) · [Installed audit](../installed-capabilities.md)

The October 29, 2026 audit inspected both installed Shows, their real sensor
HALs, current Android permissions and Home Assistant entities. Read the
[measured baseline and priority plan](../installed-capabilities.md) before
choosing another app or enabling another service.

![Observed hardware and proposed room-session coordination](../assets/room-capabilities.svg)

- [Room use cases](../room-endpoint-capabilities.md): alerts, doorbell, calls,
  media, Bluetooth speaker, BLE, presence, offline timers and resource ownership.
- [Remote access](../android-remote-access.md): existing ADB, bundled OpenSSH,
  optional Termux, SFTP, scrcpy and local automation.
- [Permissions and limits](../android-permissions-and-limits.md): actual grants,
  optional access, kiosk/owner distinctions and reversible feature acceptance.
- [Sanitized inventory](../data/capabilities-2026-10-29.json): selected measured
  facts without device identifiers, credentials or household readings.

The diagram distinguishes observed capabilities from proposed coordination
work. Lux is real and already exposed in HA. Bluetooth sink playback and SSH
login are candidates requiring tests. Missing sensor hardware cannot be
created by granting more permissions. Heavy computation stays on the home
server; each room activity should release its resources and restore the clock
and voice listener when it ends.

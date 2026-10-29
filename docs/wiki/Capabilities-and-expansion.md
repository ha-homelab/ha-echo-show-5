# Capabilities and expansion

[Wiki home](Home.md) · [Current delivery](../room-capability-delivery.md) · [Original audit](../installed-capabilities.md)

Start with the [current capability delivery register](../room-capability-delivery.md)
for the deployed r15 interface, current media clients, physical results and remaining
limits. The [room endpoint](Room-endpoint.md) links to its configuration and control
contracts; the [runtime diagram](../assets/room-runtime.svg) summarizes those paths.

The original October 29, 2026 audit inspected both Shows, their real sensor HALs,
Android permissions and Home Assistant entities **before** the subsequent room
implementation and media rollout. Its app differences and untested candidates
remain preserved as historical evidence, not current status:

- [Measured baseline and original priorities](../installed-capabilities.md).
- [Original room-use-case list](../room-endpoint-capabilities.md): alerts,
  doorbell, calls, media, Bluetooth, BLE, presence, timers and resource ownership.
- [Original access assessment](../android-remote-access.md) and the
  [implemented administration tools](../remote-admin-tools.md).
- [Permission checkpoint and Android limits](../android-permissions-and-limits.md).
- [Sanitized original inventory](../data/capabilities-2026-10-29.json): selected
  measurements without device identifiers, credentials or household readings.

![Original inventory and then-proposed room coordination](../assets/room-capabilities.svg)

This retained diagram shows the original observations and proposed work. Later
implementation and Bluetooth results belong to the delivery register above.
Missing sensor hardware still cannot be created by granting permissions. Keep
physical acceptance separate from an installed package, and keep heavy computation
on the existing server infrastructure.

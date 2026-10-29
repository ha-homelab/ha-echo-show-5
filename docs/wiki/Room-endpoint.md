# Room endpoint

The five-inch room interface combines a readable clock with six fixed controls, status readings, expiring reminders and timers. Camera motion waits for a decoded frame before replacing the clock; connection failures remain silent.

- [Complete capability delivery register](../room-capability-delivery.md)
- [Room interface configuration](../room-panel.md)
- [HA session policy and typed actions](../room-session-policy.md)
- [Remote screen and administration](../remote-admin-tools.md)

![Runtime paths](../assets/room-runtime.svg)

Keep physical acceptance separate from application installation. Native calls, background microphones and media players share one small device; the documented guards do not create an Android-wide atomic lock.

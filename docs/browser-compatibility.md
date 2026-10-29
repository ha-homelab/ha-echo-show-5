# Clock and authentication browser acceptance

The shared TypeScript workflow runs the actual `integrations/show5-display`
HTML, CSS and JavaScript. The adapter supplies a local HTTP server, a synthetic
Home Assistant WebSocket peer and a synthetic native token callback. It never
contacts Home Assistant, cameras, a voice service or a physical Show.

Every pull request requires five targets: current Chromium, Firefox and WebKit
on Linux, Chromium on Windows, and WebKit on macOS. Release candidates use all
35 targets in the [reviewed matrix](https://github.com/ha-homelab/ha-echo-show-5/blob/main/.github/browser-compatibility.json):
three pinned Playwright/browser generations across those operating systems,
plus Chrome and Edge stable/beta channels where configured. Beta releases use
the five required targets. Scheduled and manual source audits run all 35. The shared workflow checks actual browser, operating
system and Playwright identities and retains traces, screenshots and results.

Fourteen scenarios cover all four UI locales, both hour formats, 960×480 and
480×240 layouts, an observable clock tick, unsupported-locale fallback, a decoded
synthetic camera snapshot and timed return to the clock. Authentication cases
exercise recovery from `unknown_command`, permanent subscription denial,
credential refresh after invalid authentication, and pagehide/pageshow cleanup.
Only a fake native bridge is installed; the application's authentication,
WebSocket, timers, rendering and storage behavior execute in the browser.

For releases, the browser job downloads the **same immutable artifact ID** that
contains the staged integration-source archive. The existing release receipt
binds its archive digest to source SHA, workflow run and attempt. A bounded
streaming reader checks the existing explicit source inventory, rejects links
and unexpected members, and requires all nine source display files to match
that exact checkout before testing their extracted bytes. This includes
`room.js` and `offline-worker.js`; the synthetic test configuration is generated
separately. A missing, modified or
misattributed candidate blocks the build workflow and therefore publication.

These desktop engines do **not** establish Android System WebView, native
`externalApp`, audio, physical wake-word or real-camera acceptance. Those remain
separate checks described in the [validation guide](wiki/Validation.md). The
configuration defines required coverage; only a successful retained run is
proof that a particular revision passed it.

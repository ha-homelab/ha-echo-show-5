# Changelog

## [0.1.6] - Unreleased

### Room endpoint expansion

- Add optional six-button room controls, compact live readings, reminders, local timer journals and a scoped offline static cache.
- Keep the clock visible until the first decoded camera frame; suppress connection and failure overlays.
- Preserve already dispatched room actions across app-launch visibility changes, so successful commands do not report a false failure.
- Use successful live static responses even if offline-cache opening, lookup or writing fails.
- Add device-bound room actions, quiet-hour announcements, timer overdue reconciliation, session/health status and native-call guards.
- Add direct-LAN and existing-SSH administration tools, bounded scrcpy and verified SendspinDroid artifacts.
- Document feature readiness and physical-test limits in the complete capability register and runtime diagram.


### Changed

- Update the FCC cloud adapter to hash-locked grpcio 1.84.1 and refresh the pinned Debian Bookworm host-image base.
- Keep reusable workflow references and runtime inputs aligned, with verified upstream ref metadata and a single Renovate owner for GitHub Actions updates.
- Use the reviewed Ubuntu mirror fallback in browser CI and release-archive checks, preserving the required browser matrix.

### Upgrade

Rebuild only the source components you operate, following their existing installation instructions. Preserve operator configuration and the previous verified package for rollback. This source-suite release does not flash firmware or install an APK or container automatically.

### Security

Dependency hashes, TLS verification and the public source inventory remain required. The isolated Home Assistant test environment still pins Pillow 12.3.0; its upstream constraint remains open. Synthetic, browser and source-build checks do not establish physical audio, firmware or installation acceptance.

## [0.1.5] - Unreleased

### Fixed

- Keep setuptools 84.2.1 explicitly pinned and hash-locked in the FCC cloud adapter dependency set, so the strict-hash Docker installation includes its required build dependency.

### Changed

- Validate native voice routing against Home Assistant 2026.10.3 and its compatible uv 0.13.5 dependency. The source-suite version changes independently from component and external artifact versions.

### Upgrade

Use the documented installation procedure for the components you operate, retaining the previous package and configuration for rollback. This release distributes reviewed source; it does not flash firmware or install an APK or container automatically.

### Security

The cloud dependency update resolves the reported setuptools advisory in that dependency set. Home Assistant still requires Pillow 12.3.0 in the isolated test environment; the separate upstream constraint remains open. Synthetic and isolated tests do not replace physical audio or installation acceptance.

## [0.1.4] - 2026-10-24

### Added

- Optional **Hey Jarvis** activation alongside the existing exact ONNX
  **Privet Myshka** path in VACA `0.13.4+myshka.9` (7009). One microphone
  supplies both paths; Jarvis shares the existing MicroFrontend with local
  Stop. Stop remains a separate playback command.
- Preserve Jarvis's calibrated decision: mean probability over five model
  evaluations must be strictly greater than 0.97. Myshka retains its separate
  0.50 threshold, and both activation phrases share the existing cooldown.
- Require 62 passing JVM tests, including auxiliary selection, routing,
  decision preservation, listener cancellation, shutdown cleanup and
  disabled-model regressions.
  Add Android checks for shared-frontend parity, synthetic Jarvis activation
  and detector cleanup.

### Documentation

- Add a reversible mixed-wake setup and acceptance guide, an accessible SVG
  processing diagram, and updated entry points in all five README languages.
- Separate current build and device evidence from the earlier single-phrase
  checkpoints. Synthetic replay does not establish spoken recognition in a room.
- Include the referenced guides and illustrations in the source archive and
  check local documentation links after extraction.

### Fixed

- Wait for the previous wake listener to finish cleanup before starting its
  replacement; release the handler's controller when it stops.
- Keep a disabled wake listener idle and avoid constructing an OpenWakeWord
  engine when its primary model is unavailable. Preserve the existing
  microWakeWord fallback to a valid secondary model.
- Complete camera and sensor cleanup even when wake-listener shutdown times
  out. Preserve the failure for the caller instead of reporting a successful
  stop, and remove the duplicate camera-stop call.
- Keep temporary packaging repositories from running automatic Git maintenance
  during test cleanup.

### Changed

- Update the pinned CodeQL actions to 4.39.0.

### Upgrade

Build with the retained application signing identity, preserve a verified
private backup, and follow the [mixed-wake update procedure](docs/wiki/Mixed-wake-words.md).
The optional secondary selection can be removed without downgrading the APK
or replacing the exact Myshka model. Existing TLS verification, primary manifest
validation and selected Home Assistant speech services remain unchanged.

### Security

The beta distributes the integration-source suite. It excludes firmware, APKs,
private models, recordings, credentials and signing keys. Existing artifact
checksums, TLS checks and release provenance gates remain required. Physical
voice acceptance and updates to unavailable devices remain separate work.

## [0.1.3] - 2026-10-18

### Changed

- Replace the obsolete Scorecard CI container with the reviewed, checksum-pinned scanner. Keep the upstream SARIF reporting policy, GitHub Security upload and retained report artifacts.
- Synchronize the source-suite version; packaged runtime behavior is unchanged.

### Upgrade

Unpack the verified integration-source archive into a new directory. Preserve private configuration, audio, models and the previous accepted archive for rollback. Existing component versions and device installation procedures remain unchanged.

### Security

The replaced CI image contained 25 high-severity dependency findings in the recorded scan. The scanner replacement changes CI tooling, not the distributed application runtime. OpenSSF REST publication remains disabled as before. The released source suite excludes firmware, APKs, prebuilt containers and operator state. No device, audio or acoustic acceptance is claimed.

## [0.1.2] - 2026-10-17

### Changed

- Route short play and stop requests through native music controls, improve dual-wake lifecycle and add the exact ONNX wake frontend.
- Update the FCC runtime and preserve its Python 3.11 dependency lock; improve speech contention handling and bounded energy context.
- Validate the exact packaged display across supported browsers and operating systems. Preserve LF browser-asset bytes in Windows checkouts so strict archive verification succeeds without weakening the check.
- Bound artifact downloads, preserve verified concurrent results and validate VACA release metadata and classifier output. Exercise both Android source builds in CI.
- Expand localized setup and rollout documentation and license original tools under MIT while retaining upstream notices.

### Added

- Opt-in exact ONNX frontend for a private single-phrase Privet Myshka model,
  with hash-bound artifacts, deterministic streaming features and a local Stop
  detector sharing the microphone. VACA build `0.13.4+myshka.4` (7004) retains
  the separate two-model microWakeWord configuration.
- Private-fixture Android parity checks and nine additional JVM framing tests;
  the builder now requires at least eighteen passing JVM tests.
- Two simultaneous microWakeWord activation models in the pinned VACA Android
  patch, sharing one microphone, threshold and cross-model cooldown.
- English, Russian, German and Spanish clock interface catalogs and README
  entry points, plus a navigable repository wiki and accessible SVG diagrams.
- Offline documentation checks and release-archive checks for the display and
  dual-wake builder, including catalog, lifecycle and provenance regressions.

### Fixed

- Validate release JSON asset types and ONNX scalar probability outputs in VACA
  `0.13.4+myshka.6` (7006); handle nullable IPv4 addresses and remove a redundant
  volume conversion. Eight malformed-input JVM regressions supplement the
  existing TLS/build checks. Android API deprecations remain visible.

- Restore default certificate and hostname validation in the VACA application
  and custom-file downloader; require real TLS trust/rejection tests when
  building `0.13.4+myshka.5` (7005). Existing explicit compatibility opt-in
  stays local to configured clients.

- Retain custom wake models in the inventory when optional exact-frontend
  display metadata fails validation; keep actual engine loading strict.

- Yield during quiet exact-ONNX audio processing so microphone mute changes
  reach the active collection even when no detection events are emitted.
- Bound artifact download writes to the pinned size, reject HTTPS downgrades and
  invalid metadata, use private unique temporary files and preserve concurrent
  destination files until their size, digest and archive checks pass.

- Retry unavailable MQTT subscription commands during HA startup instead of
  permanently treating them as denied access. Keep permission failures blocked.
- Release the native wake detector when recognition stops or reloads. The local
  Android build is `0.13.4+dualwake.2` (7002); installation is a separate step.
- Allow guarded private build/signing paths in extracted source archives while
  retaining Git-ignore enforcement for checkouts and rejecting symlink escapes.
- Reject unexpected source changes and missing/mismatched signing identities
  during Android builds. Preserve the existing key for ordinary APK updates.

### Documentation

- Add three self-contained SVG diagrams for the exact audio pipeline, guarded
  rollout and development evaluation, with an illustrated process/results wiki
  page linked from all five README languages. Keep hardware acceptance separate
  from training, build and replay results.
- Add Russian, German, Spanish and French README entry points with a shared topic
  index, translation policy and accessible SVG architecture diagram.
- Distinguish the EchoLocal, EchoMuse and Android Show routes and label recorded
  validation as historical evidence rather than current device state.
- Include the new documentation in the public source distribution.

### Upgrade

This is the integration-source suite, not a firmware image, APK, pretrained model or prebuilt container. Follow the existing component-specific build and installation instructions; preserve private credentials, local configuration and the previous accepted artifacts for rollback. Update matching component inputs together. Publication does not deploy services, flash a device or activate a new wake model.

- Deploy clock revision `20261015-r11` with its new `i18n.js` asset and a fresh
  entry/asset version. Existing settings retain English and 24-hour time.
- Use the [same-signature update procedure](integrations/vaca-dual-wake/README.md)
  for existing local builds. Initial migration from upstream has a different
  signing identity and requires verified private data backup/restoration.
- See [validation evidence](docs/wiki/Validation.md) for the distinction between
  source checks, installed-state checks and pending physical voice acceptance.

### Security

The suite retains strict candidate-source byte checks and verifies download provenance and size bounds. VACA TLS defaults preserve verified transport. Browser, voice, source-build and loopback checks do not claim physical-device, acoustic, provider or production deployment acceptance.

## [0.1.1] - 2026-10-14

### Changed

- Validate each public release candidate with bounded, network-isolated fuzz campaigns against its exact source revision.
- Require positive engine execution counts, instrumented production code and validated seed corpora; retain source-bound reports and diagnostic evidence.
- Run deterministic seed and configuration checks in ordinary CI without starting mutation campaigns on betas.

### Upgrade

Use the existing installation procedure, preserve local configuration and keep the previous accepted package for rollback. This maintenance release updates release validation and does not change the application configuration format. Deployment and applicable device or integration acceptance remain separate from publication.

### Security

RC publication rejects absent or invalid source-bound fuzz reports. The fuzz runner bounds corpus paths, file types and size. No application vulnerability or new target-device acceptance is claimed by these tooling changes.

## [0.1.0]

### Added

- Introduce versioned integration-source beta/RC archives with an explicit file
  inventory, isolated archive checks, frozen version plans and Linux intercom
  fuzz evidence. Component and external artifact versions remain independent.

### Upgrade

extract the source suite separately, preserve private configuration,
  and follow each integration’s installation steps. This does not flash devices,
  install APKs, update Home Assistant or deploy containers.

### Security

publication binds checked bytes and source identity; synthetic
  validation does not establish physical audio or installation acceptance.

- Lock Python dependencies and verify downloaded archive SHA-256 hashes in CI and
  documented installation commands.
- Update the isolated Home Assistant test runtime from 2026.9.1 to 2026.10.0,
  which requires PyJWT 2.15.1 instead of vulnerable PyJWT 2.13.0. See
  [GHSA-ffc3-869f-jxw9](https://github.com/advisories/GHSA-ffc3-869f-jxw9)
  and the related upstream advisories. This changes the synthetic test environment;
  it does not install or upgrade Home Assistant on a user's device. Maintain an
  independently updated, supported Home Assistant installation.


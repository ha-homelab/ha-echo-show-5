# Changelog

## [Unreleased]

### Added

- Two simultaneous microWakeWord activation models in the pinned VACA Android
  patch, sharing one microphone, threshold and cross-model cooldown.
- English, Russian, German and Spanish clock interface catalogs and README
  entry points, plus a navigable repository wiki and accessible SVG diagrams.
- Offline documentation checks and release-archive checks for the display and
  dual-wake builder, including catalog, lifecycle and provenance regressions.

### Fixed

- Restore default certificate and hostname validation in the VACA application
  and custom-file downloader; require real TLS trust/rejection tests when
  building `0.13.4+dualwake.3` (7003). Existing explicit compatibility opt-in
  stays local to configured clients.

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

### Upgrade

- Deploy clock revision `20261015-r11` with its new `i18n.js` asset and a fresh
  entry/asset version. Existing settings retain English and 24-hour time.
- Use the [same-signature update procedure](integrations/vaca-dual-wake/README.md)
  for existing local builds. Initial migration from upstream has a different
  signing identity and requires verified private data backup/restoration.
- See [validation evidence](docs/wiki/Validation.md) for the distinction between
  source checks, installed-state checks and pending physical voice acceptance.

### Documentation

- Add Russian, German, Spanish and French README entry points with a shared topic
  index, translation policy and accessible SVG architecture diagram.
- Distinguish the EchoLocal, EchoMuse and Android Show routes and label recorded
  validation as historical evidence rather than current device state.
- Include the new documentation in the public source distribution.

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


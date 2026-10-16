# Maintenance, documentation and releases

[Wiki home](Home.md) · [Contributing](../../CONTRIBUTING.md) · [Release policy](../../RELEASING.md)

The project combines original tooling with pinned external software. Keep the deployed artifact, source patch, configuration and test evidence traceable without publishing local secrets or downloaded binaries.

## Source and deployment are separate

A committed change is not a deployed change. An APK build is not a successful device update. A GitHub release is not hardware acceptance. Record each stage explicitly and keep the matching rollback material.

- **Firmware and downloaded APKs:** retain the pinned metadata and upstream provenance, fetch separately, verify before use. Do not add downloads to Git to make a fresh checkout appear self-contained.
- **VACA dual-wake patch:** retain the pinned upstream revision and local signer privately. Review selection, cooldown and microphone lifecycle tests when changing the patch. Do not mix unreviewed source changes into the build checkout.
- **VACA HA patches:** source hashes intentionally fail closed when upstream changes. Re-review dashboard and timeout patches after integration updates; do not regenerate expected hashes solely to suppress a mismatch.
- **Display assets:** use a complete versioned release including `i18n.js`, keep a private prior release, and update the per-device home path. Test decoded camera video and cleanup after a UI change.
- **Voice services:** provider availability, quota and model routing can change independently of this repository. Revalidate complete recognition → dialogue → speech before a manual backend switch.

## Private information stays private

Use the ignored `private/`, `downloads/`, `vendor/`, `backups/` and `logs/` locations for local material. Keep signing keys, tokens, Wi-Fi data, host keys, full device inventories, audio, transcripts and household-specific mappings out of commits and screenshots. Secrets must not appear in command arguments or public HA `/local` assets.

Before publishing, inspect the staged file list and diff. Ignore rules do not remove tracked files or erase history. Use the [security process](../../SECURITY.md) for a discovered exposure rather than copying the secret into a public issue. The [security design](../security-design.md) explains the runtime trust boundaries.

## Documentation layout and diagrams

The four root README files are user entry points. `docs/wiki/` provides task-based navigation and links to canonical implementation runbooks. `docs/assets/` contains editable, accessible SVG diagrams with no remote fonts, scripts or embedded screenshots. Keep diagram text and its surrounding prose aligned when a data path changes.

Validation records must identify their date and scope. Keep historical observations as historical; link a newer record rather than rewriting an old test as if it ran against a later build. Do not graph service latency samples as an acoustic benchmark or invent uptime/accuracy percentages without a measured dataset.

## Optional GitHub Wiki publication

The repository-hosted wiki is complete as committed source; a separate GitHub Wiki is **optional** and is not automatically published by this change. GitHub's `.wiki.git` repository is distinct from the application repository and has different relative-link roots.

If a maintainer chooses to publish there:

1. Check that the repository's Wiki feature is enabled and initialize it through the normal GitHub flow if needed.
2. Clone the wiki repository into an ignored private working directory. Preserve existing pages; review a page-level diff rather than replacing the whole wiki blindly.
3. Copy the wiki Markdown pages and `_Sidebar.md`. Rewrite wiki-page links for the target wiki, and rewrite `../`/`../../` source links to the chosen application repository revision. Make diagram URLs point to the corresponding committed assets.
4. Verify navigation and image rendering in the target layout, then publish the reviewed wiki commit. Record the application source revision from which the copy was made.

Do not describe the separate Wiki as synchronized unless that publish and verification step actually ran. Source-relative links in this directory are designed for browsing the application repository.

## Checks and releases

Run `python3 scripts/check_docs.py` from the repository root to check local Markdown targets, anchors and accessible SVG structure. It is an offline check; it does not verify provider availability or render a page on the device.

Run the affected offline suites and documentation checks, then follow [CONTRIBUTING](../../CONTRIBUTING.md). The [CI workflow](../../.github/workflows/tests.yml) and release policy are authoritative for required jobs; a local smoke test is not a substitute for them.

This repository's release artifact is the **integration-source suite**, not firmware, a signed APK or a prebuilt device image. [Release packaging](../release-packaging.md) defines its inventory. [Versioning](../VERSIONING.md), [release operations](../release-workflow.md), [RC fuzzing](../fuzzing.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md) cover publication and provenance. Do not bypass required checks to publish a documentation refresh.

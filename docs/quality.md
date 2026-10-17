# Quality evidence and limitations

Host, browser and integration CI exercise public source packaging, conversion
preconditions, display/intercom helpers and synthetic voice behavior. Voice
runtime locks are separate environments and must be audited as such. Source
verification does not imply a physical microphone, camera or flashing acceptance.

Assess conversion, artifact download, voice/cloud, local integration and release
paths together. The complete dependency and transport review remains work in
progress; no universal TLS policy, whole-project coverage percentage or clean
full-runtime advisory inventory is claimed. See [security design](security-design.md)
and the [security policy](../SECURITY.md).

The primary maintainer personally confirms knowledge of secure design and common
Python/network application vulnerabilities, and no bug, feature or vulnerability
reports outside GitHub in the preceding twelve months as of 2026-10-16. These are
human attestations, not automated findings. Public issue history and current
diagnostics must also be reviewed for each assessment update.

## Current Android source builds

The [required Android job](../.github/workflows/android-source-builds.yml)
builds both maintained patch sets against their exact documented upstream
commits. The VACA builder applies the current dual-wake patch, requires all
nine JVM tests, compiles the ARMv7 APK and verifies package/version/ABI/signature
with an ephemeral CI-only signing identity. CI retains only its public build
receipt, never the key or APK. The OTT job applies both current patches, runs
their source regressions and compiles/audits the unsigned Full APK, including
the HTTPS hardening absent from the historical installed build.

These are source build checks using Python, Node/npm, Gradle, OpenJDK and the
Android SDK; no device, deployment, microphone or model-accuracy acceptance is
implied. The existing documented local commands remain usable. Rebuilding
external unchanged ROMs or third-party APKs is not part of these owned-patch
builds. Dependency vulnerability review remains a separate obligation.

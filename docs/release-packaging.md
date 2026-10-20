# Integration-source packaging and acceptance

The `ha-echo-show-5-<package-version>.tar.gz` asset is a source distribution of
the reviewed repository tools and integration suite. It contains the intercom
custom component and browser cards, display resources, FCC voice sources and
hash-locked requirements, portable examples, tests, upstream artifact manifests
and installation documentation. The exact files are listed in
[`release-files.json`](../release-files.json). Adding a file to Git does not add
it to a published archive; the inventory requires an explicit review.

Downloaded firmware, APKs, host binaries, private mappings, credentials, backups,
device recordings and local runtime state are not release inputs. The upstream
manifests describe separately acquired artifacts; they do not make this archive
a firmware image. This release does not deploy any service, flash or connect to
a device, modify Home Assistant, or make live voice/provider requests.

## Version ownership

`SOURCE_VERSION` versions this source suite, initially `0.1.0`. It is distinct
from the independently versioned FCC bridge, cloud adapter and intercom component
and from every upstream firmware/APK version. Those versions and dependency
hashes remain unchanged. The release policy declares the suite's text field and
the corresponding text member inside the actual archive.

The explicit promotion profile is `promote-bytes`. For example, a beta is tagged
`v0.1.0-beta.7` and carries suite version `0.1.0-beta.7`. An RC is tagged
`v0.1.0-rc.7` and carries suite version `0.1.0` so a later approved promotion can
retain its exact bytes. Preserve the tag, source SHA, manifest and checksums;
the suite version alone does not uniquely identify a candidate.

The allocator freezes a source- and policy-bound `.release-plan.json` before
building. Every build downloads that plan and synchronizes the owned version
input. Its temporary overlay and effective input digest are recorded in
`.release-inputs.json`; they are not committed back to the source branch. See
[the shared versioning contract](VERSIONING.md) and
[the release runbook](release-workflow.md) for allocator, retry and publication
rules. A failed run can consume a sequence number; never reset the ledger or
invent a replacement plan.

## Build and verification

The source adapter reads only regular tracked files from the exact inventory.
Missing files, symlinks, linked parent directories and oversized inputs fail
before packaging. File ordering, permissions and archive timestamps are
normalized. The adapter creates the archive and `SHA256SUMS`, then validates
every member and byte against the build overlay before extracting it into a
private temporary directory.

The source-distribution regression also checks every shipped Markdown link and
SVG, including the preview and full-size targets of linked images, against the
extracted inventory. Documentation images, their provenance and the release
runbooks travel with the archive. Repository-only workflow and matrix references
link explicitly to GitHub rather than pretending those files are bundled.

The extracted distribution runs the real intercom Python suite, display Python
suite, offline voice-tool help and intercom browser tests using its own files.
This proves that these shipped sources and resources work together outside the
checkout. All existing CI remains required, including Python 3.8/3.11 tools,
display JavaScript, FCC protocol tests, locked container tests, the isolated
Home Assistant 2026.10 runtime and CodeQL. The archive smoke check is an
additional boundary, not a substitute for those checks.

After verification, the staging command inspects the archive's suite version
and writes a receipt for its exact bytes and checksums. The publisher rejects
missing or inconsistent receipts. RC publication also requires the bounded
Linux intercom campaign described in [fuzzing](fuzzing.md); replaying the corpus
locally does not count as a completed mutation campaign.

To reproduce an accepted candidate, use a disposable checkout of its exact
source SHA and restore its saved plan. With Python 3.12 and Node 22 available:

```sh
python3 scripts/version_plan.py sync --plan .release-plan.json
python3 scripts/package_source.py 0.1.0 rc
python3 scripts/stage_release_assets.py --target package --pattern 'release-dist/*'
```

Use the plan's actual base and channel. The commands build and test local files;
they do not publish or deploy. Without a plan, a development archive may use
consistent base metadata, but it cannot receive a publication receipt. Existing
output directories must be empty; do not mix artifacts from separate runs.

## Installation and acceptance

The archive can validate its documentation without Git:

```sh
python3 scripts/check_docs.py --inventory
```

This checks the shipped paths and local links only; it does not fetch remote URLs.
The release-publishing commands above require the full source checkout and its
release tooling, not just the integration-source archive.

Download the exact beta/RC asset and its published manifest, verify its SHA-256,
and extract it to a new directory. Follow the included component README for the
integration you intend to test. Preserve private configuration and review local
customizations before copying component or browser files into a test
installation. FCC images are built separately from their included recipes.
No prebuilt image registry or Python package index is part of this release.

Physical audio, microphone/speaker behavior, camera behavior, firmware
compatibility, provider credentials, unattended recovery and production
installation acceptance remain separate. Historical device observations in
this repository do not qualify a new candidate. Record the tested tag, source
SHA, artifact hashes, installation results and unresolved limitations before
considering stable approval. This onboarding publishes no stable release.

Any code, dependency, policy or workflow correction requires a new candidate.
Never replace an existing release asset or edit accepted evidence. Rollback
means reinstalling previously accepted immutable source plus compatible private
configuration; it does not reset the release allocator or overwrite old tags.

Dependency review compares proposed changes on pull requests and merge groups.
Push, scheduled, and manually requested candidates have no PR comparison refs,
so that step is limited to those two comparison events; all source, runtime,
package, and candidate acceptance checks still run for the release.

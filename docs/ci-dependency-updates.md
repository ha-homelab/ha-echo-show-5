# Dependency updates

GitHub Actions, application packages and container dependencies use the shared [Renovate fleet preset](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/renovate-fleet.json), selected by [`renovate.json`](../renovate.json). The central Renovate runner must include this repository in its reviewed repository inventory.

The preset keeps related CodeQL steps together and updates reusable workflow references together with their runtime and release-policy pins. Review the complete grouped change and require the existing CI checks before merging. Never fix a pin mismatch by weakening a workflow contract.

Renovate is the dependency-update path. Complete the fleet cutover only after the full dry run succeeds and the repository update settings are verified. The local configuration preserves package compatibility bounds and update schedules. Generated locks that need a source-specific regeneration workflow and qualified browser snapshots are excluded from direct updates. GitHub dependency alerts remain enabled.

If an update fails, compare all CodeQL step references and, where present, the reusable fuzz workflow SHA, its `toolkit-ref` input and `.release-policy.json` `fuzzing.toolkit_ref`. They must agree within their respective groups.

Keep the version comment on every SHA-pinned action (`# vX.Y.Z`) and the `# main` comment on toolkit workflow references. Renovate uses these comments as version metadata; removing them can make a dependency ineligible for updates even though the workflow still executes. Verify the upstream tag-to-SHA mapping before restoring a missing version comment.

## Source-build dependency update boundary

The Renovate runner forbids package build-backend execution. The following inputs
and generated locks must therefore be reviewed and regenerated together in the
existing controlled build environment; this also applies to security updates.
GitHub vulnerability alerts remain enabled. Independent build, test and CI
dependencies retain their configured automatic update paths.

- `tests/requirements-voice.in` and `tests/requirements-voice.txt`: the pinned Home Assistant voice test environment requires pyric without a usable wheel.

Use the existing regeneration command for each pair, then run its current CI
validation before accepting the source and lock together:

```sh
uv pip compile tests/requirements-voice.in --generate-hashes --universal --python-version=3.14.2 --output-file=tests/requirements-voice.txt
```

Do not make the shared update runner execute source builds to bypass this
boundary. Requalify native ownership only when the complete pinned dependency
closure can be resolved without build-backend execution.

## Security fixes for manually maintained locks

For a direct or transitive advisory in the manually maintained environment,
identify the affected package and the advisory's fixed version range. A plain
lock regeneration may retain the existing transitive pin. Replace
`AFFECTED_PACKAGE` below with the advisory's package name and request its update
explicitly in the existing reviewed build environment:

```sh
uv pip compile tests/requirements-voice.in --generate-hashes --universal --python-version=3.14.2 --output-file=tests/requirements-voice.txt --upgrade-package AFFECTED_PACKAGE
```

Review any direct or parent constraint that prevents selection of a fixed
release; qualify that constraint change together with the lock. Preserve the
documented interpreter, platform, hash and build-isolation requirements.
Check the resulting affected-package versions against the advisory's affected
and fixed ranges in every applicable Python/platform marker branch and every
coupled lock or export. A successful resolver exit alone is not proof of a fix.
If no compatible fixed resolution exists, keep the advisory open and document
the blocker instead of marking it remediated.

Keep the Python 3.14.2 voice-test environment and its direct Home Assistant constraint aligned. Run the existing voice/HA validation before accepting the source and lock together.

Run the repository's complete existing dependency, runtime and CI qualification
before merging the source constraints and generated files together. GitHub
vulnerability alerts remain enabled for these manually maintained units.

## Riva runtime and generator ownership

The Riva cloud runtime's `grpcio` and `protobuf` updates share one branch across
major/minor versions and security updates. Native pip-compile owns
`integrations/fcc-voice-backup/cloud-requirements.in` and its hashed lock. The
existing isolated cloud tests exercise the retained generated bindings against
the new runtime; the pinned compiler check remains independent.

The generator input `integrations/fcc-voice-backup/proto-requirements.in` and its
`.txt` lock are manually maintained together with `riva_proto/UPSTREAM.json` and
the six generated Python modules in that integration. `generate_proto.py --check`
requires the exact recorded generator versions and byte-identical generated
files. Updating only a compiler lock would fail that provenance check even if
its dependency resolution succeeded. The shared updater must not run repository
generator code or weaken the source, license, or wire-descriptor checks.

For a generator dependency or security fix, select compatible versions in the
generator input and update the manifest's generator versions through independent
review. Resolve an affected transitive package explicitly, then follow the
existing separate maintenance-environment procedure:

```sh
uv pip compile integrations/fcc-voice-backup/proto-requirements.in --generate-hashes --universal --python-version=3.11 --output-file=integrations/fcc-voice-backup/proto-requirements.txt --no-build --upgrade-package AFFECTED_PACKAGE
```

Install that hash-locked compiler environment as documented in the integration's
README, run `generate_proto.py` without `--check` to regenerate all six modules,
and then run it with `--check`. Review all generated changes and preserve the
verified source/license and complete wire-descriptor hashes. Check the advisory's
fixed range for every affected resolved package and Python/platform marker; a
successful resolver exit alone does not prove remediation. If the fixed version
requires incompatible generator or runtime changes, keep the advisory open
until that complete migration is qualified. Run the existing cloud, protocol
and container CI before merging. GitHub vulnerability alerts remain enabled.

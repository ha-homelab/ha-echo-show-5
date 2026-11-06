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

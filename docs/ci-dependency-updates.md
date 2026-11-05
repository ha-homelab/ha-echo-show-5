# Dependency updates

GitHub Actions, application packages and container dependencies use the shared [Renovate fleet preset](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/renovate-fleet.json), selected by [`renovate.json`](../renovate.json). The central Renovate runner must include this repository in its reviewed repository inventory.

The preset keeps related CodeQL steps together and updates reusable workflow references together with their runtime and release-policy pins. Review the complete grouped change and require the existing CI checks before merging. Never fix a pin mismatch by weakening a workflow contract.

Renovate is the dependency-update path; Dependabot update PRs are disabled. The local configuration preserves package compatibility bounds and update schedules. Generated locks that need a source-specific regeneration workflow and qualified browser snapshots are excluded from direct updates. GitHub dependency alerts remain enabled.

If an update fails, compare all CodeQL step references and, where present, the reusable fuzz workflow SHA, its `toolkit-ref` input and `.release-policy.json` `fuzzing.toolkit_ref`. They must agree within their respective groups.

Keep the version comment on every SHA-pinned action (`# vX.Y.Z`) and the `# main` comment on toolkit workflow references. Renovate uses these comments as version metadata; removing them can make a dependency ineligible for updates even though the workflow still executes. Verify the upstream tag-to-SHA mapping before restoring a missing version comment.

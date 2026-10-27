# CI dependency updates

GitHub Actions dependencies use the shared [Renovate CI preset](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/renovate-ci.json), selected by [`renovate.json`](../renovate.json). The central Renovate runner must include this repository in its reviewed repository inventory.

The preset keeps related CodeQL steps together and updates reusable workflow references together with their runtime and release-policy pins. Review the complete grouped change and require the existing CI checks before merging. Never fix a pin mismatch by weakening a workflow contract.

The GitHub Actions section in [Dependabot configuration](../.github/dependabot.yml) explicitly disables competing Actions updates. Existing non-Actions update policies are preserved. Dependency alerts remain enabled.

If an update fails, compare all CodeQL step references and, where present, the reusable fuzz workflow SHA, its `toolkit-ref` input and `.release-policy.json` `fuzzing.toolkit_ref`. They must agree within their respective groups.

Keep the version comment on every SHA-pinned action (`# vX.Y.Z`) and the `# main` comment on toolkit workflow references. Renovate uses these comments as version metadata; removing them can make a dependency ineligible for updates even though the workflow still executes. Verify the upstream tag-to-SHA mapping before restoring a missing version comment.

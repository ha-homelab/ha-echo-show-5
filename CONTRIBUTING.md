# Contributing

Use [GitHub issues](https://github.com/ha-homelab/ha-echo-show-5/issues) for non-sensitive bug reports, questions and
feature proposals. Include the exact version/commit, environment, expected and
actual behavior, and a minimal sanitized reproduction. Check existing issues
first and keep follow-up evidence in the original thread. For vulnerabilities,
use the [private security process](SECURITY.md).

Submit a focused pull request against `main`. Describe the user-visible problem,
the resulting behavior, compatibility implications and checks performed. Preserve
existing authorship and third-party license/provenance records. Discuss changes
to protocols, storage, device safety or dependency/runtime requirements before
making an incompatible change. English is the common language for code review
and project documentation.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s integrations/show5-intercom/tests -v
node --test integrations/show5-display/tests/*.cjs
python3 -m unittest discover -s integrations/show5-display/tests -p 'test_*.py' -v
```

CI separates synthetic host tests, frontend lifecycle tests and optional voice-runtime environments. Use the workflow-specific Python requirements for those environments. These commands do not install firmware, access a camera or approve a live rollout.

The [CI workflow](.github/workflows/tests.yml) is the authoritative list of required jobs.
Use isolated test data and temporary outputs. Never run a device write, unlock,
deployment or publication command merely to validate a documentation change.

## Test and review policy

Changes to behavior must add or update automated tests that fail for the old
defect and cover the new boundary; regression fixes should include the relevant
failure case. If automation is infeasible, explain why in the PR and document
the reproducible manual procedure and limits. Update user/API documentation and
release notes for user-visible changes. Keep compiler, lint, static-analysis and
test assertions enabled, resolve new warnings, and document any remaining
warning with its reason and scope. Do not suppress a real security finding to
obtain a passing check. Wait for required checks and independent review before
merging; do not use an administrator bypass.

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
and the canonical technical documentation. Translated README entry points and
the display's English, Russian, German and Spanish catalogs are maintained
together; see [localization](docs/wiki/Localization.md) and the
[translation policy](docs/i18n.md). Keep code identifiers,
commands and device model names unchanged in translations.

## Development and validation

```sh
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s integrations/show5-intercom/tests -v
node --test integrations/show5-display/tests/*.cjs
python3 -m unittest discover -s integrations/show5-display/tests -p 'test_*.py' -v
python3 -m unittest discover -s integrations/vaca-dual-wake/tests -v
python3 scripts/check_docs.py
```

CI separates synthetic host tests, frontend lifecycle tests and optional voice-runtime environments. Use the workflow-specific Python requirements for those environments. These commands do not install firmware, access a camera or approve a live rollout.

The offline documentation check verifies local Markdown links, heading anchors
and accessible, self-contained SVG diagrams. It does not fetch external links.
Keep new shipped files in the explicit `release-files.json` inventory; a new
script referenced by HTML must also be present in the source distribution.

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

## Reproducible Python dependencies

The `.in` files declare direct dependencies. The corresponding `.txt` files pin
all resolved dependencies and approved archive SHA-256 hashes across supported
platforms. Install with `--require-hashes`; do not remove this check to work around
a missing archive. Review dependency updates and regenerate the locks with:

```sh
uv pip compile integrations/fcc-voice-backup/requirements.in --generate-hashes --universal --python-version 3.11 --output-file integrations/fcc-voice-backup/requirements.txt
uv pip compile integrations/fcc-voice-backup/cloud-requirements.in --generate-hashes --universal --python-version 3.11 --output-file integrations/fcc-voice-backup/cloud-requirements.txt
uv pip compile tests/requirements-voice.in --generate-hashes --universal --python-version 3.14.2 --output-file tests/requirements-voice.txt
```

Run the documented tests in a fresh virtual environment after updating a lock.
The isolated Home Assistant test runtime is 2026.10.0 and requires Python
3.14.2 or newer. Updating these test dependencies does not upgrade an installed
Home Assistant instance.

Contributions to original project code and documentation are made under the [MIT license](LICENSE). Preserve upstream copyright, license and NOTICE files for third-party material.


All major functionality changes must include automated regression coverage and
relevant negative cases, with test instructions documented in the PR. Resolve
substantive compiler, linter and security-analysis findings before merge. Do not
replace actual device acceptance with synthetic test success.

See [governance](GOVERNANCE.md), [conduct](CODE_OF_CONDUCT.md),
[security reporting](SECURITY.md) and the [roadmap](ROADMAP.md).

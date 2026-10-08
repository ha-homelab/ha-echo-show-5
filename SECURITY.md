# Security policy

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/ha-homelab/ha-echo-show-5/security/advisories/new).
If the form is unavailable, contact a maintainer through the repository's GitHub
profile to arrange a private channel before sharing sensitive details. Public
issues are for non-sensitive defects and feature requests.

Include the affected commit/release, prerequisites, a minimal synthetic
reproduction, expected and actual results, and impact. Do not include live
credentials, personal data or access to devices you do not own.

## Response and supported versions

Maintainers aim to acknowledge a private report within 14 days, investigate its
scope, and agree on remediation and disclosure with the reporter. If no reply
arrives within 14 days, follow up privately. Confirmed security defects are
prioritized by impact; critical defects take precedence over feature work.

Security fixes target the current default branch and latest published release,
where one exists. Older snapshots are not maintained security branches. Release
notes must identify security fixes, affected versions and upgrade actions without
disclosing credentials. This policy is a commitment for handling reports, not
a claim that no vulnerabilities exist or that past reports met a response SLA.

## Project boundary

This project provides Echo Show 5 Gen2 conversion and Home Assistant display, voice and intercom helpers.

Raw backups, Android/ADB access, Home Assistant tokens, microphones and cameras are sensitive. Follow the attended conversion order and validate backups before destructive writes. Restrict ADB and remote endpoints to authenticated trusted clients. Voice activation is not identity verification. Camera/voice availability and privacy controls require physical-device checks beyond synthetic frontend and protocol tests.

See [security design and validation boundaries](docs/security-design.md).

# Security policy

## Reporting a vulnerability

Use [GitHub private vulnerability reporting](https://github.com/ha-homelab/ha-echo-show-5/security/advisories/new).
If the form is unavailable, email **alvit.work@gmail.com** privately. Public
issues are for non-sensitive defects and feature requests.

Include the affected commit/release, prerequisites, a minimal synthetic
reproduction, expected and actual results, and impact. Do not include live
credentials, personal data or access to devices you do not own.

## Response and supported versions

Maintainers aim to acknowledge a private report within 14 days, investigate its
scope, and agree on remediation and disclosure with the reporter. If no reply
arrives within 14 days, follow up privately. Confirmed security defects are
prioritized by impact. Critical vulnerabilities are handled immediately; known
medium-or-higher vulnerabilities in supported project results are fixed within
60 days of public disclosure. If an upstream fix is unavailable, document a
reviewed mitigation or disable the affected supported path rather than calling
the entire dependency environment clean.

Security fixes target the current default branch and latest published release,
where one exists. Older snapshots are not maintained security branches. Release
notes must identify security fixes, affected versions, available CVE/GHSA
identifiers and upgrade actions without disclosing credentials. Credit reporters
of fixed vulnerabilities unless they request anonymity. Coordinate disclosure
with the reporter and preserve private reproduction details. This policy is a commitment for handling reports, not
a claim that no vulnerabilities exist or that past reports met a response SLA.

## Project boundary

This project provides Echo Show 5 Gen2 conversion and Home Assistant display, voice and intercom helpers.

Raw backups, Android/ADB access, Home Assistant tokens, microphones and cameras are sensitive. Follow the attended conversion order and validate backups before destructive writes. Restrict ADB and remote endpoints to authenticated trusted clients. Voice activation is not identity verification. Camera/voice availability and privacy controls require physical-device checks beyond synthetic frontend and protocol tests.

See [security design and validation boundaries](docs/security-design.md).

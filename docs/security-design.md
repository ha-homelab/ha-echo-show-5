# Security design and verification

## Scope and trust boundaries

The project provides Echo Show 5 Gen2 conversion and Home Assistant display, voice and intercom helpers.

Raw backups, Android/ADB access, Home Assistant tokens, microphones and cameras are sensitive. Follow the attended conversion order and validate backups before destructive writes. Restrict ADB and remote endpoints to authenticated trusted clients. Voice activation is not identity verification. Camera/voice availability and privacy controls require physical-device checks beyond synthetic frontend and protocol tests.

## Source and operating documentation

- [scripts/rawbackup.py](../scripts/rawbackup.py)
- [scripts/prepare_amonet.py](../scripts/prepare_amonet.py)
- [scripts/remote.py](../scripts/remote.py)
- [docs/preparation-status.md](../docs/preparation-status.md)

## Regression evidence

- [tests/test_guards.py](../tests/test_guards.py)
- [tests/test_rawbackup.py](../tests/test_rawbackup.py)
- [tests/test_remote_endpoint.py](../tests/test_remote_endpoint.py)
- [integrations/show5-display/tests/test_auth.cjs](../integrations/show5-display/tests/test_auth.cjs)

Run the documented commands in [CONTRIBUTING.md](../CONTRIBUTING.md) and the
[CI workflow](../.github/workflows/tests.yml). Preserve negative tests for rejected inputs,
unavailable dependencies, authorization failures and cancellation. A passing
test run describes its fixtures and environment; it does not certify every
upstream service, hardware model or production deployment.

## Remaining security assessment

An explicit project-source license grant is absent. Resolve source ownership and license choice, including third-party conversion artifacts, before claiming FLOSS eligibility. Preserve pending physical voice/power-cycle acceptance from the existing runbook.

Report new issues through [SECURITY.md](../SECURITY.md). An OpenSSF assessment
records evidence and applicability; it is not a guarantee that a system is safe.

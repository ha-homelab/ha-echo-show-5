# Changelog

## Unreleased

- Lock Python dependencies and verify downloaded archive SHA-256 hashes in CI and
  documented installation commands.
- Update the isolated Home Assistant test runtime from 2026.9.1 to 2026.10.0,
  which requires PyJWT 2.15.1 instead of vulnerable PyJWT 2.13.0. See
  [GHSA-ffc3-869f-jxw9](https://github.com/advisories/GHSA-ffc3-869f-jxw9)
  and the related upstream advisories. This changes the synthetic test environment;
  it does not install or upgrade Home Assistant on a user's device. Maintain an
  independently updated, supported Home Assistant installation.


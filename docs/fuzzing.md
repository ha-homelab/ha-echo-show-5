# Bounded intercom validation

See the [illustrated RC fuzzing process and verified rollout results](https://github.com/victron-venus/venus-os-ci-toolkit/blob/main/docs/rc-fuzzing-results.md)
for the shared release flow, evidence requirements and a dated cross-project
snapshot. The project-specific scope and reproduction guidance below still apply.

The `intercom-boundaries` target calls the actual `decode_pcm` and
`LeaseGuard.require` implementations. Arbitrary input exercises strict base64
and PCM16 bounds; independently generated synthetic PCM must round-trip. Typed
JSON queries exercise connection owner, token, mode and expiration checks against
a synthetic in-memory lease. No acquire/end operation, callback, timer, network
connection, microphone, speaker, USB device or Home Assistant runtime is started.
The four injected resource hooks raise if accidentally reached.

The target budget is 60 seconds with a 4096-byte input limit. Requirements are
hash-locked to Atheris 3.1.0 for Linux/x86-64. The existing intercom test workflow
also replays the committed synthetic corpus without the mutation engine. Local
replay does not establish a completed Linux mutation campaign.

```sh
python3.11 -m unittest discover -s integrations/show5-intercom/tests -p test_fuzz_oracle.py -v
```

The existing lifecycle, cancellation, frontend, display, FCC and HA runtime tests
remain necessary; this bounded target adds coverage for the pure boundaries.
Live audio quality, physical controls, firmware compatibility, cloud-provider
behavior and installation acceptance are outside this target.

The positive `pcm.txt` corpus fixture is strict Base64 without a trailing line
ending. Its unit test checks that the exact committed bytes decode to 1,764 zero
PCM bytes, so a text edit cannot silently convert this accepted case into a
rejected-input test. The other corpus cases exercise lease ownership; the oracle
also generates valid PCM from each input to check round-trip behavior.

## Release integration

The shared release pipeline runs this Linux target for RC candidates and binds
its immutable result to the exact source commit and frozen release plan. A
failed or missing campaign prevents RC publication. Beta source archives still
run the full application and packaging checks but do not claim RC fuzz evidence.
See [source packaging and acceptance](release-packaging.md) for the explicit
inventory and separate installation/hardware acceptance requirements.


## Deterministic preflight in ordinary CI

For relevant changes in a public repository, the existing CI configuration
contract job installs the hash-locked Python 3.12 fuzz dependencies, runs
`pip check`, and replays the committed corpus with Atheris `-runs=0`.
This is deterministic seed replay: it does not start the timed mutation
campaign. Timed fuzzing remains exclusive to release candidates. The shared
preflight has a four-minute total budget, including dependency setup.

The `preflight-paths` entries in `.github/fuzz.json` select the relevant
production, dependency and harness changes. Shared contract, manifest and
workflow changes also trigger this check; missing comparison history runs
the check conservatively. Unrelated changes can skip this extra replay.

Before replay, the shared helper verifies that the following declarations
refer to project-local Python functions already instrumented by the
harness. Missing import instrumentation fails the check instead of
silently counting executions with incomplete feedback:

- `lease.decode_pcm`
- `lease.LeaseGuard.require`

Update these declarations when production functions move or are renamed.
They prove that the selected code is instrumented; they do not prove
exhaustive path coverage. Keep positive and rejected-input corpus cases
and independent semantic assertions alongside the existing unit tests.

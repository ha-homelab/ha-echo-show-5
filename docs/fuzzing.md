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

## Public release artifacts and retries

Fresh public package uploads and RC fuzz evidence use
`-run-<run_id>-attempt-<run_attempt>` artifact names. The candidate and final
collectors select that same run and attempt.

Before publication starts, use **Re-run all jobs** only if the allocator and
release policy permit reuse of that run's reservation. Recreate every required
input in the same attempt; failed-only or individual retries can leave inputs
missing, and older artifacts must not fill those gaps.

For a fresh candidate or final build, once publication has started
(`begin_publication`), or its external publication result is partial or uncertain,
inspect the existing release, tags and assets before retrying. A consumed build
number requires a new workflow run and reservation authorized by the release
policy; an existing immutable tag may also require a new base version. Never
reset the release ledger, overwrite assets or retag to force a retry. Historical
byte promotion of an accepted RC keeps its reserved number and follows the
existing promotion policy.

Mutation remains limited to an explicit RC dispatch on the public default
branch. Its report describes one source revision and run; it does not establish
complete platform coverage or device acceptance. See the shared
[evidence contract](rc-fuzzing.md).

Browser validation still downloads the package through its exact artifact ID;
the separate `browser-release` evidence names and workflow pin are unchanged.
Package receipts additionally bind fresh publication to the current repository,
source SHA, workflow run and attempt. The declared package receipt inventory is
checked before publication; historical promotion retains its existing checks.

### Complete package producer inventory

`versioning.required_build_receipts` declares the exact package and signature
receipt filenames required by this project's final publisher. Each authenticated
receipt must match the repository, source commit, workflow run and attempt. A
missing producer or an unexpected receipt stops fresh publication, even when the
remaining packages are valid. RC fuzz evidence is checked separately; pre-signing
checks do not require a signature receipt that has not been created yet.

Before publication begins, rerun all required producers only when the allocator
and release policy permit reusing that reservation. After publication begins or
its outcome is uncertain, inspect existing tags, releases and assets before a
policy-authorized new run; never reset the ledger or mix earlier-attempt packages.
Historical RC promotion keeps its accepted source policy. Keep this explicit
inventory aligned with producer changes; it does not replace package-format,
signature or device acceptance checks.

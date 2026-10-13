# Bounded intercom validation

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

## Release integration

The shared release pipeline runs this Linux target for RC candidates and binds
its immutable result to the exact source commit and frozen release plan. A
failed or missing campaign prevents RC publication. Beta source archives still
run the full application and packaging checks but do not claim RC fuzz evidence.
See [source packaging and acceptance](release-packaging.md) for the explicit
inventory and separate installation/hardware acceptance requirements.

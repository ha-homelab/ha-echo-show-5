# Bounded intercom validation

The prepared `intercom-boundaries` target calls the actual `decode_pcm` and
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

## Release integration design

The next lifecycle should package an explicit source inventory of the owned
integration suite, voice routing tool, tests and required integration resources.
It must verify an isolated archive's imports and browser resources before issuing
a receipt. A new source-suite version must be distinct from third-party amonet,
LineageOS, firmware, APK and host-tool versions; none of those external binaries
may be claimed as an owned source release. Existing upstream manifests and
operator-only ignored directories must retain their boundaries.

This target configuration is prepared but is not yet connected to a shared RC
workflow. That workflow must preserve every current required test job, pin a
durable toolkit merge commit and bind Linux results to the exact source plan.
Publication of source beta/RC assets must not call deployment, unlock, flashing,
ADB, audio or cloud-provider operations. No stable or device-acceptance claim is
part of this preparation.

# FCC voice backup

Three small services connect the independent FCC voice path alongside Homeway: our authenticated FCC gateway, a Wyoming conversation bridge and a Wyoming cloud-audio adapter. No local speech or language model runs here.

Read [deployment and switching](../../docs/fcc-voice-backup.md), [cloud audio](../../docs/fcc-cloud-audio.md) and [the model shortlist](../../docs/fcc-audio-models.md). Cloud audio uses NVIDIA Parakeet ASR and Russian Chatterbox TTS with the existing operator credential; conversation uses FCC's selected external text route. The conversation bridge has no Home Assistant tools or credentials.

[Assistant behavior](../../docs/fcc-assist-behavior.md) describes the 0.1.4
classification-first prompt for Russian answers, explicit background-speech suppression and
bounded spoken replies. Native HA intents still handle device commands before
the text fallback; updating this bridge does not add device tools to the model.

```bash
python3.11 -m venv private/voice-tools
private/voice-tools/bin/pip install --require-hashes -r integrations/fcc-voice-backup/requirements.txt \
  --require-hashes -r integrations/fcc-voice-backup/cloud-requirements.txt
private/voice-tools/bin/python -m unittest discover -s integrations/fcc-voice-backup/tests -v
```

The gateway URL must use HTTPS outside exact loopback hosts (`localhost`, `127.0.0.1`, `::1`) or the trusted Kubernetes `*.svc.cluster.local` network. The supplied internal gateway URL remains valid; arbitrary LAN or remote HTTP endpoints are rejected before requests can send transcripts or bearer credentials. Allowed internal HTTP traffic is plaintext and relies on the trusted cluster network and its network policy; this exception does not provide TLS encryption.

The conversation bridge uses `FCC_BASE_URL`, `FCC_API_KEY_FILE`, an explicit free `FCC_MODEL`, and `FCC_TIMEOUT_SECONDS` (1–60; default 30), listening on `WYOMING_URI` (default `tcp://0.0.0.0:10400`).

The cloud adapter uses `NVIDIA_API_KEY_FILE` and `NVIDIA_RPC_TIMEOUT_SECONDS` (1–30; default 30), listening on TCP 10500. It fixes its TLS provider target, model routes and Russian voice; it does not load a local model or enable arbitrary URLs/SSML. Independent ASR and TTS pools default to two operations each (`FCC_ASR_CONCURRENCY` and `FCC_TTS_CONCURRENCY`, integer 1–4). Bounded input/output, real RPC deadlines and cancellation protect the service.

Keep both unauthenticated Wyoming listeners inside trusted infrastructure. Provider keys, filled manifests and raw evidence stay outside Git. The images and Kubernetes manifests are separate so cloud-audio rollout does not restart the conversation path or Homeway.

## Dependency compatibility

The cloud adapter installs `cloud-requirements.txt` as one runtime environment:
Wyoming 1.10.2, gRPC 1.85.1 and protobuf 6.33.5. It uses six local generated
protocol modules under `riva_proto`, not the full NVIDIA client SDK. The runtime
therefore does not install the SDK's unused WebSocket client or `grpcio-tools`.
The provider, TLS settings, request limits and ASR/TTS behavior are unchanged.

The four protocol sources are copied from
[NVIDIA Riva common, commit 268890b7](https://github.com/nvidia-riva/common/tree/268890b7286031a6d4950e34f7ce13ed0d4ce621),
with the original [MIT license](riva_proto/LICENSE). Their complete protobuf
wire descriptors match the descriptors shipped by NVIDIA client 2.27.0.
[UPSTREAM.json](riva_proto/UPSTREAM.json) records source and descriptor hashes.
Only Python imports and Python class module names are relocated to `riva_proto`;
protobuf package names, field numbers and service paths remain unchanged.

Regenerate the runtime lock for the Python version in `Dockerfile.cloud`
(currently 3.14):

```bash
uv pip compile integrations/fcc-voice-backup/cloud-requirements.in --generate-hashes --universal --python-version 3.14 --output-file integrations/fcc-voice-backup/cloud-requirements.txt
```

Install that lock in a clean environment with `--require-hashes`, run
`python -m pip check`, then run `test_cloud_speech.py`. The tests check that the
SDK, WebSocket library and generator are absent from the runtime. Existing local
gRPC and Wyoming tests exercise actual serialization, failure handling and
cancellation without contacting a speech provider.

### Updating the protocol bindings

Generation is an explicit maintenance operation in a separate environment:

```bash
tools_dir=$(mktemp -d)
python -m venv "$tools_dir"
"$tools_dir/bin/python" -m pip install --require-hashes -r integrations/fcc-voice-backup/proto-requirements.txt
"$tools_dir/bin/python" integrations/fcc-voice-backup/generate_proto.py --check
```

Run the generator without `--check` to rewrite the six modules. It reads only
the four vendored sources, checks their hashes and the resulting descriptors,
and does not download source code. Regeneration is byte-for-byte reproducible;
CI checks it in an isolated tool environment before testing the runtime.
Remove the temporary tool environment when finished.

To change the source revision, review the full upstream schema diff and update
its source hashes, descriptor compatibility evidence and license deliberately.
Regenerate and review all six modules, then rerun the complete cloud and container
tests. Updating dependencies alone must not silently change the wire schema.
The separate maintenance lock is regenerated with:

```bash
uv pip compile integrations/fcc-voice-backup/proto-requirements.in --generate-hashes --universal --python-version 3.11 --output-file integrations/fcc-voice-backup/proto-requirements.txt
```

These source changes do not deploy an image or change a device.


Optional energy grounding is described in [assistant behavior](../../docs/fcc-assist-behavior.md#optional-read-only-energy-context).
It requires an explicitly configured IGW URL and scoped read token; it is off by
default and grants no device-control permission.

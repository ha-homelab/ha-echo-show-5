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

The cloud adapter installs `cloud-requirements.txt` as one environment. Riva
2.27 requires protobuf **6.33.5** and websockets **>=15.0.1,<16**. The compatible
gRPC tools line is **1.82**: 1.83 and later require protobuf 7.35.1 or newer.
Dependabot groups this runtime and excludes those incompatible ranges while
leaving compatible updates eligible. Revisit the bounds when Riva changes its
requirements, including for a security-driven migration; resolve the complete
environment and run `test_cloud_speech.py` before merging. Updating these files
does not deploy an image or change a device.

Regenerate the hash-locked runtime for the Python version in `Dockerfile.cloud`
(currently 3.14), including transitive build helpers required at runtime:

```bash
uv pip compile integrations/fcc-voice-backup/cloud-requirements.in --generate-hashes --universal --python-version 3.14 --output-file integrations/fcc-voice-backup/cloud-requirements.txt
```

Install the result into a fresh environment with `--require-hashes`, then run
`python -m pip check` and the cloud speech tests. A developer environment with
preinstalled `setuptools` can otherwise hide an incomplete lock.


Optional energy grounding is described in [assistant behavior](../../docs/fcc-assist-behavior.md#optional-read-only-energy-context).
It requires an explicitly configured IGW URL and scoped read token; it is off by
default and grants no device-control permission.

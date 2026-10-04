# FCC voice backup

Three small services connect the independent FCC voice path alongside Homeway: our authenticated FCC gateway, a Wyoming conversation bridge and a Wyoming cloud-audio adapter. No local speech or language model runs here.

Read [deployment and switching](../../docs/fcc-voice-backup.md), [cloud audio](../../docs/fcc-cloud-audio.md) and [the model shortlist](../../docs/fcc-audio-models.md). Cloud audio uses NVIDIA Parakeet ASR and Russian Chatterbox TTS with the existing operator credential; conversation uses FCC's selected external text route. The conversation bridge has no Home Assistant tools or credentials.

```bash
python3.11 -m venv private/voice-tools
private/voice-tools/bin/pip install -r integrations/fcc-voice-backup/requirements.txt \
  -r integrations/fcc-voice-backup/cloud-requirements.txt
private/voice-tools/bin/python -m unittest discover -s integrations/fcc-voice-backup/tests -v
```

The gateway URL must use HTTPS outside exact loopback hosts (`localhost`, `127.0.0.1`, `::1`) or the trusted Kubernetes `*.svc.cluster.local` network. The supplied internal gateway URL remains valid; arbitrary LAN or remote HTTP endpoints are rejected before requests can send transcripts or bearer credentials. Allowed internal HTTP traffic is plaintext and relies on the trusted cluster network and its network policy; this exception does not provide TLS encryption.

The conversation bridge uses `FCC_BASE_URL`, `FCC_API_KEY_FILE`, an explicit free `FCC_MODEL`, and `FCC_TIMEOUT_SECONDS` (1–60; default 30), listening on `WYOMING_URI` (default `tcp://0.0.0.0:10400`).

The cloud adapter uses `NVIDIA_API_KEY_FILE` and `NVIDIA_RPC_TIMEOUT_SECONDS` (1–30; default 30), listening on TCP 10500. It fixes its TLS provider target, model routes and Russian voice; it does not load a local model or enable arbitrary URLs/SSML. One shared audio operation, bounded input/output, real RPC deadlines and cancellation protect the service.

Keep both unauthenticated Wyoming listeners inside trusted infrastructure. Provider keys, filled manifests and raw evidence stay outside Git. The images and Kubernetes manifests are separate so cloud-audio rollout does not restart the conversation path or Homeway.

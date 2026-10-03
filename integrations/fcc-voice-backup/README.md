# FCC Voice Backup

Stateless Wyoming → FCC conversation bridge and our authenticated FCC gateway. These two services form the prepared conversation backup for Homeway; no local speech model is deployed.

Read the [deployment, limits and switching guide](../../docs/fcc-voice-backup.md) and [model shortlist](../../docs/fcc-audio-models.md). The bridge handles recognized or typed text; it does not itself add an audio endpoint to FCC. Independent cloud audio integration remains pending. It has no Home Assistant tools or credentials.

```bash
python3.11 -m venv private/voice-tools
private/voice-tools/bin/pip install -r integrations/fcc-voice-backup/requirements.txt
private/voice-tools/bin/python -m unittest discover -s integrations/fcc-voice-backup/tests -v
```

Set `FCC_BASE_URL` to the gateway origin and `FCC_API_KEY_FILE` to its proxy token file. Optional settings are `FCC_MODEL` (explicit FCC OpenRouter `:free` ID), `FCC_TIMEOUT_SECONDS` (1–60; default 30) and `WYOMING_URI` (default `tcp://0.0.0.0:10400`). Restrict the unauthenticated Wyoming listener to trusted HA clients. Keep provider keys, filled manifests and evidence outside Git.

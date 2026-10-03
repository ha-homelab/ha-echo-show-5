# FCC cloud audio alongside Homeway

Home Assistant can keep Homeway and FCC registered at the same time. Each Assist
pipeline selects its own speech recognition, conversation and synthesis engines.
A satellite selects one pipeline for an interaction; registering another provider
does not change that selection. See [HA's pipeline API](https://developers.home-assistant.io/docs/voice/pipelines/)
and [Wyoming integration](https://www.home-assistant.io/integrations/wyoming/).

## Independent FCC path

The FCC path uses three small services on the designated worker:

1. `fcc-cloud-speech` exposes Wyoming on TCP 10500. It sends audio to NVIDIA's
   hosted Parakeet multilingual ASR and answer text to NVIDIA's hosted Chatterbox
   Russian TTS using the existing operator credential.
2. `fcc-voice-bridge` exposes Wyoming conversation on TCP 10400 and sends recognized
   text to the authenticated FCC gateway.
3. `fcc-voice-gateway` serves FCC HTTP on TCP 8082 and routes conversation to the
   explicitly selected external free text model.

Homeway has its own pipeline and providers. The FCC pipeline does not call Homeway
for either recognition or synthesis. Local Whisper/Piper remain stopped. No model
is downloaded to the worker: these services handle protocol and network traffic.

The cloud adapter follows the same NVIDIA Parakeet route used by FCC's existing
provider-owned voice-note backend and adds a bounded HA audio entrypoint. It does
not add audio support to FCC's `/v1/messages` schema. Chatterbox TTS is supplied by
this adapter; it is not claimed to be a built-in FCC conversation feature.

Audio goes to NVIDIA for recognition, unmatched transcript text goes through FCC
to its selected external text provider, and answer text goes to NVIDIA for speech
synthesis. HA local intents handle supported commands before the conversation
fallback. The FCC conversation bridge has no HA token or home-control tools.

## Provider configuration

The adapter fixes its TLS gRPC target to `grpc.nvcf.nvidia.com:443` and uses two
provider-documented routes:

- ASR: `nvidia/parakeet-1.1b-rnnt-multilingual-asr`, Russian `ru-RU`.
- TTS: Chatterbox multilingual, voice `Chatterbox-Multilingual.ru-RU.Male`,
  Russian `ru-RU`, 22,050 Hz mono PCM16.

Russian recognition is listed in [the Parakeet model card](https://build.nvidia.com/nvidia/parakeet-1_1b-rnnt-multilingual-asr/modelcard).
Chatterbox Russian support is listed in [NVIDIA's speech support matrix](https://docs.nvidia.com/nim/speech/latest/reference/support-matrix/tts.html).
The existing NVIDIA credential worked in bounded synthetic tests. This does not
establish unlimited quota, reset timing or guaranteed free production access.
NVIDIA describes its hosted access as [prototyping access](https://docs.api.nvidia.com/nim/docs/product);
provider terms and data handling apply. No paid fallback is configured.

## Build and register

```bash
docker build -f integrations/fcc-voice-backup/Dockerfile.cloud \
  -t fcc-cloud-speech:0.1.0 integrations/fcc-voice-backup
```

Import this image into the selected node's k3s/containerd store before applying
`integrations/fcc-voice-backup/k8s/cloud-speech.yaml`. The image uses
`imagePullPolicy: Never`; a workstation Docker image is insufficient. The existing
FCC gateway and bridge do not need rebuilding for this audio adapter.

Namespace `homeassistant` and Secret `fcc-cloud-speech-credentials` must exist.
Its single key, `nvidia-api-key`, comes from the existing private FCC credential
store. Mount it only in the cloud adapter; do not copy it into HA, an Echo app,
container image or repository. `NVIDIA_API_KEY_FILE` names the mounted file;
`NVIDIA_RPC_TIMEOUT_SECONDS` defaults to 30 and accepts 1–30 seconds.

Add **Wyoming Protocol** in HA with host
`fcc-cloud-speech.homeassistant.svc.cluster.local`, port `10500`. It advertises
both STT and TTS under **FCC Cloud Speech**. Then configure the existing
**FCC Russian Backup** assistant with:

- Language: Russian; prefer handling commands locally.
- Conversation: FCC Voice Backup.
- STT: FCC Cloud Speech, language `ru`.
- TTS: FCC Cloud Speech, language `ru`, voice `Chatterbox-Multilingual.ru-RU.Male`.

Keep the existing Homeway pipeline and all satellite selections unchanged while
validating. Both providers can be loaded without restarting HA or reconnecting USB.
Use the [guarded switching workflow](fcc-voice-backup.md#switch-one-or-several-satellites)
when deliberately selecting a device. Do not remove either integration to switch.

## Bounds and failure behavior

The cloud adapter keeps audio in memory and does not log audio, transcripts,
credentials or raw provider errors. Its Wyoming listener is unauthenticated and
must stay on trusted internal networking; ClusterIP is not authentication.
The accepted gateway policy does not isolate the separate audio listener.

- One shared in-flight audio operation across capture, ASR and TTS; overlapping
  operations fail busy rather than accumulating a queue.
- ASR accepts only mono PCM16 at 16 kHz, up to 30 seconds. Capture has a 45-second
  total deadline and 10-second idle deadline. Frames, connections and allocations
  are bounded before payload reads.
- Every ASR RPC has a real gRPC deadline. TTS shares one deadline across all
  chunks, so splitting a response cannot multiply the configured timeout.
- TTS accepts at most 1,000 plain-text characters, splits at sentence/word
  boundaries into at most ten chunks of at most 200 characters, and rejects SSML
  and unbroken oversized tokens. NVIDIA's normalization can still cause a
  provider rejection; it is reported, not silently truncated.
- Synthesis buffers at most 60 seconds of PCM before sending audio. A later failed
  chunk produces an error instead of a partially spoken answer. Client disconnect
  cancels the RPC and releases the shared operation slot.
- There is no automatic retry, provider substitution or Homeway fallback.

The existing Google Translate TTS integration also produced Russian test audio;
it remains an optional, manually selected provider, not a dependency of this path.
HA documents it as an [unofficial Google Translate speech engine](https://www.home-assistant.io/integrations/google_translate/).

## Validation

On 2026-10-03 the deployed adapter registered as `stt.fcc_cloud_speech` and
`tts.fcc_cloud_speech` in HA. The existing FCC assistant was completed with these
engines and the Russian voice above. All three FCC services were Ready on the
designated worker; local Whisper/Piper remained at zero replicas. Registration
preserved Homeway, the global preference, other pipelines and satellite choices.

One simultaneous HA test sent the same 1.907-second synthetic Russian question,
"Сколько будет два плюс два?", to FCC and Homeway. Both recognized it correctly
and returned the answer four with valid downloaded audio. Measured from the end
of input audio, FCC delivered the first answer bytes in **6.443 seconds** and
the complete audio in **6.467 seconds**; Homeway took **2.664 seconds** and
**2.808 seconds**, respectively. From the start of input, the first-byte timings
were 8.354 and 4.575 seconds. FCC recognition ended 1.353 seconds after input
ended, and its conversation stage took 3.473 seconds. These are one-trial
observations, not guarantees. Earlier direct ASR probes had minor word errors.

A separate harmless time question used HA's local intent handling in about
5 milliseconds and downloaded FCC answer audio in 1.760 seconds overall.
Guarded status reported both backends ready, and the FCC switch preview passed
for all three reachable assistant selectors. Every selector stayed on Homeway;
the unavailable satellite was excluded. No audio was played on a household device.

Offline tests use real loopback Wyoming framing and local fake gRPC services.
They exercise metadata, Russian configuration, multi-segment transcription,
chunked synthesis, total deadlines, malformed/oversized input, busy behavior,
disconnect cancellation and recovery without provider credentials.

Live tests must use generated phrases, fetch answer audio without playing it on a
household device, and record STT, conversation and first-answer-audio timings
separately. Run the FCC and Homeway pipelines concurrently to verify coexistence.
`Ready`, entity availability and a TTS URL are not proof of completed audio. Physical
wake-word accuracy, microphone/speaker quality and long-term availability need an
attended device check.

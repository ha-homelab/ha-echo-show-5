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
  -t fcc-cloud-speech:0.1.3 integrations/fcc-voice-backup
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

- Separate ASR and TTS pools, each allowing two operations by default.
  `FCC_ASR_CONCURRENCY` and `FCC_TTS_CONCURRENCY` accept integers 1–4.
  An ASR slot covers capture through recognition; a TTS slot covers synthesis
  through sending the complete result. Exceeding a pool fails busy immediately;
  requests never queue. The independent eight-connection limit still applies.
- ASR accepts only mono PCM16 at 16 kHz, up to 30 seconds. Capture has a 45-second
  total deadline and 10-second idle deadline. Frames, connections and allocations
  are bounded before payload reads.
- Each ASR request and complete TTS operation opens a dedicated TLS gRPC
  connection and closes it on completion, error or cancellation. TTS segments
  share that operation's connection; ASR and TTS never share one.
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
disconnect cancellation and recovery without provider credentials. The connection
regressions also check that each operation owns a new channel, every channel
closes after completion or cancellation, and the next request succeeds after a
timeout without replaying the failed request. Run them with the hashed cloud
dependencies on Python 3.11; CI also runs them inside the pinned Python 3.14 image:

```bash
python -m pip install --require-hashes -r integrations/fcc-voice-backup/cloud-requirements.txt
python -m unittest discover -s integrations/fcc-voice-backup/tests -p test_cloud_speech.py -v
```

Live tests must use generated phrases, fetch answer audio without playing it on a
household device, and record STT, conversation and first-answer-audio timings
separately. Run the FCC and Homeway pipelines concurrently to verify coexistence.
`Ready`, entity availability and a TTS URL are not proof of completed audio. Physical
wake-word accuracy, microphone/speaker quality and long-term availability need an
attended device check.

## Recovery from stale cloud connections (2026-10-06)

Version 0.1.0 kept one gRPC connection for the process lifetime and used it for
both cloud functions. During an incident affecting two Echo Dots, four synthetic
requests through that process timed out after about 30 seconds, including both
ASR and TTS. A fresh client in the same Pod, with the same credential and routes,
recognized the fixture in 2.566 seconds and synthesized speech in 2.369 seconds.
The original process still timed out immediately after the fresh-client test.
This isolates a stale connection/session from microphone or wake-word behavior;
it does not prove the initial cause of the stale session.

Version 0.1.1 opens an isolated connection per operation and closes it in a
`finally` block. NVIDIA documents that its proxy binds sessions to TCP
connections and recommends closing a connection after use; see
[gRPC function invocation](https://docs.nvidia.com/nvcf/overview/g-rpc-function-invocation).
The change preserves the 30-second deadline, credentials, models, one-operation
limit and no-retry policy. Failure logs now include a fixed stage name, without
transcripts, audio or raw provider error messages.

An independent FCC conversation timeout also occurred in the incident. A later
synthetic text request completed in 2.111 seconds. This transport fix is for
cloud speech; it does not guarantee the availability or latency of the external
text model. Diagnose `no-speech`, a busy service and conversation timeouts
separately. Do not retune wake thresholds to compensate for a cloud timeout.

## Multi-satellite concurrency and telemetry (0.1.2)

A recording or answer synthesis no longer blocks the other operation type.
The pools are global to the service, not satellite identities: Wyoming uses a
connection for the request, and every connection retains its own audio buffer
and lease. Closing one client cancels only its RPC and releases only its slots.
A malformed request or timeout cannot free another client's capacity. Provider
quotas remain shared; increasing concurrency is not a quota increase.

Two ASR and two TTS operations require at most about 6.9 MiB for the configured
raw input/output buffers, excluding Python, gRPC and transport overhead. The
existing memory limit remains in place. No streaming semantics changed: TTS
still buffers all validated segments before emitting `audio-start`, so a later
provider failure cannot leave a partially spoken answer.

`FCC_CLOUD_SPEECH_STAGE` emits `stage=capture|asr|tts`, a fixed `outcome` and
`elapsed_ms`. Capture duration ends at `audio-stop`; ASR measures provider work
and transcript delivery; TTS includes synthesis and complete wire delivery.
Cancellation and failed operations are recorded too. These are service timings,
not microphone-to-speaker latency. Logs contain no text, audio, source IDs,
device IDs, credentials or raw provider errors. Existing fixed-category failure
logs remain available; do not count both records as separate failed requests.

Build/load `fcc-cloud-speech:0.1.2` on the selected worker and apply the reviewed
private overlay of `k8s/cloud-speech.yaml`. No HA pipeline edit or new secret is
needed. To roll back, restore the saved Deployment (including its image and env),
or select the retained `fcc-cloud-speech:0.1.1` image. An in-flight request can
fail during a rollout; do it when the satellites are idle. This source change
alone does not deploy the service.

The 2026-10-14 image build reported that the existing pinned `grpcio-tools`
1.82.0 release was yanked because of its
[protobuf dependency metadata](https://github.com/grpc/grpc/issues/42906).
The adapter uses the Riva package's shipped protobuf classes and does not invoke
`protoc`; the pinned-image gRPC tests passed. The tested lock was retained for
this rollout, including protobuf 6.33.5. This is a recorded dependency-refresh
follow-up, not a claim that the dependency set is warning-free or that code
generation with this combination is supported.

### Empty recognition results: 0.1.3

A completed recognition request can legitimately contain no recognized text.
Version 0.1.3 sends a Wyoming `Transcript` with an empty string for that result,
allowing Home Assistant to report `stt-no-text-recognized`. Earlier versions
sent `Error(no-speech)`, which HA classified as `stt-stream-failed` even though
the cloud request had succeeded. Stage telemetry still records `no-speech`;
audio and recognized text are not logged.

This change applies only after valid audio has completed recognition. Missing
or invalid audio, malformed replies, authentication failures, unavailable
providers and timeouts retain their error paths. It does not change the
conversation agent, TTS or a satellite's policy for rearming after no speech.

Build and load the new image on the selected worker before selecting it. Wait
for voice requests to finish, then update only the cloud-speech container:

```sh
kubectl -n homeassistant set image deployment/fcc-cloud-speech \
  cloud-speech=fcc-cloud-speech:0.1.3
kubectl -n homeassistant rollout status deployment/fcc-cloud-speech
```

Keep the previous image available. Roll back this change by selecting
`cloud-speech=fcc-cloud-speech:0.1.2` with the same command. No HA restart or
credential changes are required. A successful offline protocol test does not
establish live satellite acceptance; verify a normal request and a no-speech
request separately after the coordinated rollout.

### Deployed checkpoint: 2026-10-14

The reviewed source at `be6b0a6df29dc2153577a11748149d662277b514`
was built into complete Linux/amd64 images: bridge **0.1.4** and cloud speech
**0.1.2**. Both were imported into the selected worker's containerd store before
changing the two Deployments. The old bridge source overlay was removed;
credentials, gateway, HA pipeline IDs and satellite selections were preserved.
Ready Pod file hashes matched the source, and both Wyoming `Describe` replies
reported the expected versions. ASR and TTS capacity each read back as **2**.

Two synthetic recordings were held concurrently while two independent synthesis
requests started. Both recognitions completed in **2.404 / 2.535 seconds** after
`audio-stop`; both synthesis requests produced complete PCM responses in
**4.206 / 4.055 seconds** (88,642 / 86,878 bytes). The fixture asked why ice floats
in water. Both transcripts retained that question, with a spelling error in
the final word; this is not a claim of perfect recognition. No microphone was
recorded and the generated audio was not played on a household device.

These are one paired trial's service timings, not latency percentiles or a
physical-device acceptance test. The worker was busy, and shell/exec startup
was independently slow. Read-only checks found no CPU quota on the worker's
k3s service or the `kubepods` ancestors; the existing 500m Pod limits did throttle
some startup work. No host resources or unrelated workloads were changed.

Full pre-change Deployment specs were saved privately before either patch.
Rollback must restore the previous model first if it was subsequently changed,
then restore those specs, including the former bridge source mount/annotations
and the cloud adapter's old environment. Retain the old images and ConfigMap
until acceptance is complete; selecting an old bridge image alone is insufficient.

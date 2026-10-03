# FCC catalog: Russian voice and audio shortlist

Checked on **2026-10-03** against the supplied `~/fcc-models.txt` and current upstream documentation/metadata. The supplied file was left intact. Its entries mix modalities and pricing; the FCC name is a routing alias, not a promise of zero cost or audio transport.

## Selected architecture

For a Home Assistant voice backup, separate recognition from reasoning: **local multilingual Whisper → free FCC text model → local Piper**. Audio is handled by your own speech services; only recognized text goes to the external model provider. This also works around the inspected FCC HTTP API's lack of audio content/transcription support. See [deployment and switching](fcc-voice-backup.md).

## Free text candidates after local transcription

- **Liquid LFM2.5-2.6B**, catalog line 360: `anthropic/open_router/liquid/lfm-2.5-2.6b:free`. Current prompt/completion pricing is zero; input/output are text. The publisher lists Russian. This compact model is a latency candidate, not a validated general-knowledge replacement. The normal `anthropic/` alias works; the catalog's adjacent `no-thinking` alias was rejected with HTTP 400 because this endpoint requires reasoning. The bridge returns only final text. The free provider says prompts/outputs may be retained for training. [Provider listing](https://openrouter.ai/liquid/lfm-2.5-2.6b:free), [publisher card](https://huggingface.co/LiquidAI/LFM2.5-2.6B).
- **Google Gemma 4 26B A4B**, catalog line 337: `claude-3-freecc-no-thinking/open_router/google/gemma-4-26b-a4b-it:free`. A second explicit free text-response route to test for Russian quality and response latency. Do not infer FCC audio support from any upstream multimodal capability. [Current listing](https://openrouter.ai/google/gemma-4-26b-a4b-it:free).

Both depend on available free-provider capacity and the account's limits. Keep the explicit `:free` ID and disable FCC model fallbacks. A new paid model must never be substituted silently.

## Models that really accept audio upstream

- **NVIDIA Nemotron 3 Nano Omni 30B A3B reasoning**, catalog line 443: `claude-3-freecc-no-thinking/open_router/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`. Current metadata reports text/audio/image/video input and zero prompt/completion price. The free endpoint expressly excludes confidential information and personal data, including people's voices and faces, and describes logging/use for improvement. Keep it a **synthetic-only research candidate**; it is not selected for household audio. It needs a separate upstream audio adapter because FCC does not pass audio through. [Provider listing and conditions](https://openrouter.ai/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free).
- **Groq Whisper large-v3-turbo**, catalog line 836: `claude-3-freecc-no-thinking/groq/whisper-large-v3-turbo`. This is multilingual speech recognition, not a chat model or general sound-event analyzer. Groq offers a limited free tier and paid service; account limits must be checked. Actual transport is multipart `POST /openai/v1/audio/transcriptions`, with provider model `whisper-large-v3-turbo`, an audio file and `language=ru`. It cannot be selected as the FCC conversation model. An optional Groq Wyoming STT adapter would be additional work; the prepared route uses local Whisper. [Official speech documentation](https://console.groq.com/docs/speech-to-text).
- **Gemini 2.5 Flash**, catalog line 279: `claude-3-freecc-no-thinking/open_router/google/gemini-2.5-flash`. It can understand/transcribe audio upstream, but this OpenRouter route has nonzero pricing. Google's native API/free-tier eligibility is a separate route and account policy. It is excluded from this free-only standby. [Google audio documentation](https://ai.google.dev/gemini-api/docs/audio), [OpenRouter listing](https://openrouter.ai/google/gemini-2.5-flash).
- **Voxtral Small 24B**, catalog line 421: `claude-3-freecc-no-thinking/open_router/mistralai/voxtral-small-24b-2507`. An upstream audio-understanding model with nonzero OpenRouter pricing. It is not interchangeable with the dedicated Voxtral Mini transcription API. It is excluded from the free-only standby. [Provider listing](https://openrouter.ai/mistralai/voxtral-small-24b-2507).

OpenRouter audio requests use `/api/v1/chat/completions`, the upstream model ID without FCC prefixes and an `input_audio` part carrying a supported base64 audio format. That body is **not** valid audio input to the inspected FCC `/v1/messages` schema. [Audio transport documentation](https://openrouter.ai/docs/guides/overview/multimodal/audio).

Whisper produces words, not a reliable description of non-speech sounds, speakers' emotions or arbitrary recordings. If the goal later expands to “what is happening in this audio file?”, implement and test an audio-understanding adapter with a suitable provider/data policy instead of treating a transcript as the complete recording.

## Recheck before changing the model

Consult [live OpenRouter model metadata](https://openrouter.ai/api/v1/models), the route's provider conditions and [account limits](https://openrouter.ai/docs/api-reference/limits). Check exact input modalities, prompt/completion/audio pricing, actual provider availability and a bounded synthetic Russian request. Record the resolved route and full-answer latency. Never upload household recordings merely to benchmark a model. The catalog's listed Qwen routes are not assumed free; a similarly named current `:free` variant must be audited separately.

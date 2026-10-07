# FCC assistant behavior

The FCC assistant combines HA's local intent handling with a separate text
fallback. Selecting FCC retains HA's local intent handling, but does not give
the FCC model Homeway's device-control capabilities. Its independent NVIDIA
speech recognition and synthesis providers are separate from Homeway. The Wyoming
bridge has no HA token, device tools, device-state catalogue or shared chat
history. Keep **Prefer handling commands locally** enabled on the FCC pipeline.

Use HA's built-in intents and reviewed sentence automations for device actions.
For example, resuming an existing music queue and starting a particular radio
station are different actions. The latter requires a configured playable source
or a media catalogue with working search support. A model claiming that music
has started is not evidence that a player received or executed a command.
See HA's [custom sentence guide](https://www.home-assistant.io/voice_control/custom_sentences/).

## Conversation bridge 0.1.3

The system prompt now asks for direct, concise Russian answers to general
questions. It avoids unsolicited introductions, lists of capabilities and offers
to configure HA. It does not limit conversation to home automation or demand
blanket refusals for entire subjects. Uncertainty should be specific to the
question. When an unhandled device command reaches this fallback, it must say
that the action was not performed and ask for the missing device or action.

The selected free model and external provider still influence answer quality.
This prompt change does not guarantee the correctness of answers, provide live
internet access or enable model-driven home control.

Complete, valid model replies are limited to **900 spoken characters**, below
the cloud speech adapter's 1000-character input limit. Longer replies are
shortened at a sentence boundary when possible, otherwise at a word boundary,
and explicitly end with “Ответ сокращён.” Responses over the existing
4000-character generated-text limit, incomplete responses, unexpected blocks,
tool calls, SSML, invalid control characters and words longer than the speech
adapter's 200-character segment limit remain errors. Abbreviation
does not turn an invalid provider response into a successful answer.

## Background speech and false activation

The 0.1.3 prompt classifies the transcript before answering, with contrasting
Russian examples. When the transcript clearly contains an unrelated monologue or fragment with
no question, request or address to the assistant, the model may return the
exact final text `[[NO_SPEECH]]`. Only that exact result becomes an empty
Wyoming `Handled` response. Normal empty responses, partial markers, incomplete
generation and errors are not interpreted as silence. The bridge also rejects
a model's silence decision for obvious question marks and common Russian or
English question, command and greeting prefixes. Isolated function-word
fragments such as “can” may still be silent; standalone greetings and “stop”
remain requests.

The deployed HA pipeline source was checked before introducing this protocol:
the Wyoming integration accepts empty handled speech, and Assist skips TTS for
an empty answer when there is no local action acknowledgement. Confirm this
behavior with a synthetic full pipeline run after upgrading HA. A failed
provider request must still be visible as an error rather than disappearing.

This is a conservative conversation safeguard, not a wake-word or voice-activity
detector. It cannot reliably distinguish a television question from a person
asking the same words. False wakes still need separate microphone, wake-word
threshold and VAD checks. No household audio or transcripts are logged by this
bridge; synthetic examples are sufficient for regression checks.

## Build and acceptance

Run from the reviewed source checkout with the pinned Python dependencies:

```bash
python -m unittest discover -s integrations/fcc-voice-backup/tests -v
docker build --platform linux/amd64 -t fcc-voice-bridge:0.1.3 \
  integrations/fcc-voice-backup
```

Distribute the image to the deployment node before applying the source
`integrations/fcc-voice-backup/k8s/bridge.yaml`; it uses `imagePullPolicy: Never`.
Use the established private overlay and credential path. The change requires
no new secret, HA permission, external model route or provider registration.
Keep the previous image available for rollback.

Validate each behavior independently with synthetic inputs:

- A general factual question and a request for a basic legal definition produce
  useful short answers without an unrelated HA introduction or blanket refusal.
- An explicit question, a device command and a greeting are not suppressed as
  background speech. An unhandled command does not claim success.
- A clearly unrelated narrative may produce empty speech; an Assist run then
  finishes without a TTS request or spoken error.
- An exposed local device command matches an HA intent or reviewed automation,
  bypasses the external model and changes the intended device. Check real state
  and playback, not only the conversation text.
- A long valid answer fits the speech adapter. Rate limits, timeouts, overlapping
  requests, malformed answers and tool calls retain their bounded error behavior.

Unit tests cover the protocol and limits. They do not establish provider quota,
model classification quality, physical wake-word reliability or audible playback.

## Deployment checkpoint: 2026-10-04

Wyoming Describe reported 0.1.2 after a bridge-only rollout. An immutable code
overlay on the previously cached runtime was necessary because the worker's
container image import was timing out; the source and dependencies were checked.
The self-healing repository records this temporary recovery path and its rollback.

Synthetic Assist requests reached the FCC model again after an independently
recreated HA pod finished registering its conversation engine. A factual question
completed in 16.522 seconds; a request for a basic legal definition, including
cloud TTS, completed in 20.509 seconds without an unrelated setup offer or blanket
topic refusal. These are individual observations under load, not latency targets.
The factual answer contained a contradiction despite its correct opening, and
the definition had awkward wording. The first background-speech probe still
produced an unwanted reply. This led to the classification-first 0.1.3 prompt.

Six bounded classification checks of that prompt passed: the previously failing
narrative was silent twice, a new narrative and isolated “can” were silent, and
a question and implied music request were answered. Observed response times
ranged from 8.096 to 29.972 seconds. A definition response nevertheless included
an incorrect legal citation. Classification improved; these checks do not
establish factual accuracy or general reliability of the selected small free
model. Unit tests and transport success must not be presented as answer-quality
validation.

After deploying 0.1.3, Describe confirmed the new version and the same narrative
completed through the real Assist pipeline in 19.836 seconds with empty speech.
The run ended without `tts-start` or `tts-end`. This verifies the end-to-end
silence protocol for that synthetic case, not a guarantee against all false wakes.

Local origin-aware volume, explicit-target volume, clock and camera commands
were checked separately and bypassed the external model. Music playback and
physical wake-word reliability require their own device acceptance; neither is
established by a successful text response.

A separate synthetic comparison checked the explicitly free Gemma 4 31B route
listed by FCC and [OpenRouter's endpoint catalogue](https://openrouter.ai/api/v1/models/google/gemma-4-31b-it:free/endpoints).
Although the catalogue listed an available zero-token-price endpoint, the first
request exceeded the 30-second deadline (30.931 seconds observed). The comparison
stopped after that one request; neither answer quality nor suitability was
established, and the deployed model was not changed. Provider privacy terms also
need review before a different upstream receives household conversations.

// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.nearest

/** Disabled arbitration preserves the prior local wake/stop behavior of active Assist. */
internal fun nearestWakeAllowed(enabled: Boolean, canAnswer: () -> Boolean, captureAllowed: () -> Boolean): Boolean =
    if (enabled) canAnswer() else captureAllowed()

/** Share the local handler's timeout policy with coordinated wake admission.
 * Active playback and unknown stages never qualify for stale-request recovery.
 * The 16s/31s boundaries preserve the original whole-second >15/>30 checks.
 */
internal fun wakePipelineAllowsStart(stage: String?, ageMs: Long, voicePlaying: Boolean): Boolean {
    if (voicePlaying) return false
    return when (stage) {
        null, "ENDED" -> true
        "INIT", "STARTING", "STARTED", "LISTENING", "VOICE_STARTED", "VOICE_STOPPED",
        "AWAITING_RESPONSE" -> ageMs >= 16_000L
        "AWAITING_TTS", "STARTING_TTS" -> ageMs >= 31_000L
        else -> false
    }
}

// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

/** A per-player gain envelope. Removing a token never restores an old user volume. */
class OwnedMusicGain {
    var target = 1f; private set
    private var focusCap: Float? = null
    var owner: String? = null; private set
    val output: Float get() = minOf(target, focusCap ?: 1f) * if (owner == null) 1f else DUCK_FACTOR
    val focusLimited: Boolean get() = focusCap != null
    fun setTarget(value: Float) { require(value.isFinite()); target = value.coerceIn(0f, 1f) }
    fun focusLost(cap: Float) { require(cap.isFinite()); focusCap = cap.coerceIn(0f, 1f) }
    fun focusGained() { focusCap = null }
    fun begin(requestId: String): Boolean {
        if (owner != null) return false
        owner = requestId
        return true
    }
    fun end(requestId: String): Boolean {
        if (owner != requestId) return false
        owner = null
        return true
    }
    companion object { const val DUCK_FACTOR = 0.2f }
}

/** Public Android playback observations have no reliable client identity; reject ambiguity. */
internal fun ownedPlaybackObserved(kinds: List<String>, ownAnnouncement: Boolean, ownMusic: Boolean): Boolean {
    if (kinds.any { it != "music" && it != "announcement" }) return false
    val music = kinds.count { it == "music" }
    val announcements = kinds.count { it == "announcement" }
    if (!ownAnnouncement) return announcements == 0 && music == if (ownMusic) 1 else 0
    // Track registration and buffering are asynchronous. Extra observed players always fail closed.
    return announcements <= 1 && music <= if (ownMusic) 1 else 0
}

package com.msp1974.vacompanion.nearest

/** Caller holds its runtime lock. Listener pauses do not invalidate the retained transport. */
internal class NearestLifecycle {
    var revision = 0L
        private set
    var active = false
        private set
    private var requested = false
    private var transportGeneration = 0L

    fun start(): Long { requested = true; active = false; return ++revision }
    fun reload(expected: Long): Long? = if (current(expected)) start() else null
    fun current(expected: Long) = requested && revision == expected
    fun activate(expected: Long): Boolean {
        if (!current(expected)) return false
        active = true
        return true
    }
    fun pause() { requested = false; active = false; revision++ }
    fun replaceTransport(): Long { active = false; return ++transportGeneration }
    fun acceptsClaim(generation: Long) = active && generation == transportGeneration
}

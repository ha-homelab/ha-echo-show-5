package com.msp1974.vacompanion.feedback

/** Pooled audio players can deliver a stopped play's callback after their next play. */
class WakeCueOwnership {
    private var owner: Any? = null
    private var revision = 0L

    val generation: Long
        @Synchronized get() = revision

    @Synchronized
    fun begin(nextOwner: Any): Long {
        owner = nextOwner
        return ++revision
    }

    @Synchronized
    fun isCurrent(expectedOwner: Any, expectedGeneration: Long): Boolean =
        owner === expectedOwner && revision == expectedGeneration

    /**
     * Atomic completion: stale callbacks never run their side effects. Keep onRelease
     * brief and synchronous; this monitor serializes it with admission and stop.
     */
    @Synchronized
    fun release(expectedOwner: Any, expectedGeneration: Long, onRelease: () -> Unit = {}): Boolean {
        if (!isCurrent(expectedOwner, expectedGeneration)) return false
        try {
            onRelease()
        } finally {
            // A callback may reentrantly admit another play. Never invalidate it.
            if (isCurrent(expectedOwner, expectedGeneration)) {
                owner = null
                ++revision
            }
        }
        return true
    }

    @Synchronized
    fun invalidate() {
        owner = null
        ++revision
    }
}

// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

/** Pure state for a bounded UsageEvents cursor; failed scans discard partial evidence. */
internal class ForegroundState {
    data class ActivityEvidence(val focused: Boolean, val changedAt: Long)
    private var lastQuery = 0L
    private var foreground: String? = null
    private var observedAt = 0L
    fun queryStart(now: Long): Long {
        if (now < lastQuery) { foreground = null; observedAt = 0; lastQuery = 0 }
        return if (lastQuery == 0L) (now - LOOKBACK_MS).coerceAtLeast(0) else (lastQuery - OVERLAP_MS).coerceAtLeast(0)
    }
    fun resumed(packageName: String, at: Long) {
        if (at >= observedAt) { foreground = packageName; observedAt = at }
    }
    fun paused(packageName: String, at: Long) {
        if (packageName == foreground && at >= observedAt) { foreground = null; observedAt = at }
    }
    fun complete(now: Long) { lastQuery = now }
    fun failed(now: Long) { foreground = null; observedAt = now; lastQuery = now }
    fun allows(ownPackage: String, homePackage: String?, own: ActivityEvidence): Boolean {
        // Newer observed external foreground wins until the activity lifecycle catches up.
        if (own.focused && (foreground == null || foreground == ownPackage || own.changedAt > observedAt)) return true
        if (foreground == ownPackage) return false // Stale usage history cannot override actual pause/focus loss.
        return homePackage != null && foreground == homePackage && observedAt >= own.changedAt
    }
    companion object {
        const val LOOKBACK_MS = 86_400_000L
        const val OVERLAP_MS = 1_000L
    }
}

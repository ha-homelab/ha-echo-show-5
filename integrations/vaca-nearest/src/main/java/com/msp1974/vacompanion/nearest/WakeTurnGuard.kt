package com.msp1974.vacompanion.nearest

/** Generation tokens prevent delayed network/timer completions starting a superseded voice turn. */
class WakeTurnGuard {
    private var generation = 0L
    private var waiting = false
    @Synchronized fun begin(): Long? {
        if (waiting) return null
        waiting = true; return ++generation
    }
    @Synchronized fun current(token: Long) = token == generation
    @Synchronized fun finish(token: Long): Boolean {
        if (token != generation || !waiting) return false
        waiting = false; return true
    }
    @Synchronized fun cancel() { generation++; waiting = false }
}

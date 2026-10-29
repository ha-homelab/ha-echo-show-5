package com.msp1974.vacompanion.nearest

/** A local election driven by an adapter's monotonic clock; never schedules or performs I/O.
 * Call receive only after request authentication, and markAnsweredElsewhere only after proof verification.
 */
class NearestElection {
    class Pending internal constructor(val claim: NearestClaim, val atMillis: Long, val windowMillis: Long) {
        internal var answered = false
        internal var elsewhere = false
        internal var decided = false
    }
    enum class Decision { WAIT, START, YIELD, STALE }
    private data class Heard(val claim: NearestClaim, val atMillis: Long)
    private val heard = ArrayDeque<Heard>()
    private var mine: Pending? = null

    @Synchronized
    fun begin(claim: NearestClaim, atMillis: Long, windowMillis: Long = 300): Pending {
        require(claim.from.isNotEmpty() && claim.score.isFinite())
        prune(atMillis)
        return Pending(claim, atMillis, windowMillis.coerceIn(100, 500)).also { mine = it }
    }

    /** True requests a signed HTTP 409 response; otherwise respond 204. */
    @Synchronized
    fun receive(claim: NearestClaim, nowMillis: Long): Boolean {
        require(claim.from.isNotEmpty() && claim.score.isFinite())
        val current = mine
        if (current?.claim?.from == claim.from) return false
        prune(nowMillis)
        // Bound even authenticated peer traffic. Normal households have at most a few dozen claims.
        if (heard.size >= 256) heard.removeFirst()
        heard.addLast(Heard(claim, nowMillis))
        return current != null && current.answered && current.claim.word == claim.word &&
            nowMillis - current.atMillis in 0..(2 * current.windowMillis)
    }

    @Synchronized
    fun markAnsweredElsewhere(pending: Pending) {
        if (mine === pending && !pending.decided) pending.elsewhere = true
    }

    @Synchronized
    fun decide(pending: Pending, nowMillis: Long, canAnswer: Boolean = true): Decision {
        if (mine !== pending || pending.decided) return Decision.STALE
        if (nowMillis < pending.atMillis + pending.windowMillis) return Decision.WAIT
        val beaten = heard.any { it.atMillis >= pending.atMillis - pending.windowMillis &&
            it.claim.word == pending.claim.word && better(it.claim, pending.claim) }
        pending.decided = true
        pending.answered = !beaten && !pending.elsewhere && canAnswer
        return if (beaten || pending.elsewhere) Decision.YIELD else Decision.START
    }

    /** Superseding/cancelling a waiting local wake cannot open a turn when its timer fires later. */
    @Synchronized fun cancel() { mine = null }

    private fun prune(nowMillis: Long) {
        while (heard.isNotEmpty() && nowMillis - heard.first().atMillis >= 3000) heard.removeFirst()
    }

    companion object {
        fun adjustedScore(standout: Double, offsetDb: Double = 0.0, onCallWithWakeAllowed: Boolean = false): Double {
            require(standout.isFinite() && offsetDb.isFinite())
            return standout.coerceIn(0.0, 90.0) + offsetDb.coerceIn(-30.0, 30.0) + if (onCallWithWakeAllowed) 6.0 else 0.0
        }

        fun better(a: NearestClaim, b: NearestClaim): Boolean =
            if (a.score != b.score) a.score > b.score else compareUtf8(a.from, b.from) < 0

        // Go string ordering compares UTF-8 bytes, not Java UTF-16 code units.
        private fun compareUtf8(a: String, b: String): Int {
            val aa = a.toByteArray(Charsets.UTF_8); val bb = b.toByteArray(Charsets.UTF_8)
            for (i in 0 until minOf(aa.size, bb.size)) {
                val result = (aa[i].toInt() and 255) - (bb[i].toInt() and 255)
                if (result != 0) return result
            }
            return aa.size - bb.size
        }
    }
}

package com.msp1974.vacompanion.telephony

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Pure state machine. A grant follows completed capture teardown, never a mute icon. */
internal class AudioLeaseCoordinator(
    initial: Record?,
    private val now: () -> Long,
    private val persist: (Record?) -> Unit,
    private val canAcquire: () -> Boolean,
    private val snapshotMuted: () -> Boolean,
    private val prepare: suspend () -> Unit,
    private val resume: suspend () -> Unit,
) {
    data class Record(val uid: Int, val token: String, val priorMuted: Boolean,
                      val deadline: Long, val boot: Int, val phase: String)
    data class Result(val ok: Boolean, val state: String, val token: String = "", val reason: String = "")
    private val mutex = Mutex()
    @Volatile private var record: Record? = initial
    @Volatile var inhibited: Boolean = initial != null
        private set

    fun status(uid: Int): Result {
        val r = record ?: return Result(true, "idle")
        return Result(true, r.phase, if (r.uid == uid) r.token else "", if (r.uid == uid) "" else "busy")
    }

    suspend fun acquire(uid: Int, token: String, ttl: Long, boot: Int): Result = mutex.withLock {
        requireToken(token); require(ttl in 10_000L..60_000L)
        val old = record
        if (old != null) return@withLock Result(false, old.phase, if (old.uid == uid) old.token else "", "busy")
        // Gate all creation/restart paths before checking current ownership and stopping capture.
        inhibited = true
        val ready = try { canAcquire() } catch (e: Exception) {
            inhibited = false
            throw e
        }
        if (!ready) {
            inhibited = false
            return@withLock Result(false, "idle", reason = "voice_or_media_busy")
        }
        val muted = try { snapshotMuted() } catch (e: Exception) {
            inhibited = false
            throw e
        }
        var r = Record(uid, token, muted, now() + ttl, boot, "acquiring")
        try {
            persist(r); record = r
            prepare()
            r = r.copy(phase = "held")
            persist(r); record = r
            Result(true, "held", token)
        } catch (e: Exception) {
            // Teardown may have partially completed: do not restart by guessing.
            r = r.copy(phase = "recovery")
            record = r
            runCatching { persist(r) }
            Result(false, "recovery", token, "capture_not_released")
        }
    }

    suspend fun renew(uid: Int, token: String, ttl: Long): Result = mutex.withLock {
        requireToken(token); require(ttl in 10_000L..60_000L)
        val r = record
        if (r == null || r.uid != uid || r.token != token) return@withLock Result(false, "idle", reason = "not_owner")
        if (r.phase != "held" || r.deadline <= now()) return@withLock Result(false, r.phase, token, "expired")
        val next = r.copy(deadline = now() + ttl)
        persist(next); record = next
        Result(true, "held", token)
    }

    /** Deadline is revocation, not evidence that a live client has released its AudioRecord. */
    suspend fun expire(): Record? = mutex.withLock {
        val r = record ?: return@withLock null
        if (r.phase != "held" || now() < r.deadline) return@withLock null
        val revoked = r.copy(phase = "revoked")
        persist(revoked); record = revoked
        revoked
    }

    /** Caller promises its native call is Released/Core.stop completed, or its Binder died. */
    suspend fun release(uid: Int, token: String): Result = mutex.withLock {
        requireToken(token)
        val r = record ?: return@withLock Result(true, "idle", token)
        if (r.uid != uid || r.token != token) return@withLock Result(false, r.phase, reason = "not_owner")
        try {
            val restoring = r.copy(phase = "recovery")
            persist(restoring); record = restoring
            inhibited = false
            resume()
            persist(null); record = null
            Result(true, "idle", token)
        } catch (e: Exception) {
            inhibited = true
            // A failed journal clear may follow successful recorder startup.
            // Close that capture again before advertising blocked recovery.
            runCatching { prepare() }
            record = r.copy(phase = "recovery")
            runCatching { persist(record) }
            Result(false, "recovery", token, "restoration_failed")
        }
    }

    private fun requireToken(token: String) {
        require(token.length in 16..80 && token.all { it.isLetterOrDigit() || it == '-' || it == '_' })
    }
}

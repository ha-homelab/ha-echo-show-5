// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

/** Durable idempotency within the retained window; pruning persists an expiry fence. */
internal class AnnouncementLedger(
    initial: List<Record>,
    private val wallNow: () -> Long,
    private val monotonicNow: () -> Long,
    private val persist: (List<Record>, Long) -> Unit,
    private val busyReason: () -> String?,
    private val capacity: Int = 2048,
    initialPrunedThrough: Long = 0,
) {
    data class Record(val requestId: String, val fingerprint: String, val expiresAt: Long,
                      val status: String, val reason: String = "", val busyPolicy: String = "skip")
    data class Reply(val requestId: String, val status: String, val reason: String = "", val fresh: Boolean = false)
    private val records = LinkedHashMap<String, Record>()
    private var deadline: Long = 0
    private var prunedThrough: Long = initialPrunedThrough
    @Volatile var healthy: Boolean = true
        private set
    val current: String? get() = synchronized(AnnouncementGate.monitor) { records.values.lastOrNull { it.status in ACTIVE }?.requestId }
    val canAcceptNew: Boolean get() = synchronized(AnnouncementGate.monitor) {
        healthy && wallNow() > prunedThrough &&
            (records.size < capacity || records.values.any { prunable(it, wallNow()) })
    }
    init {
        require(capacity > 0 && initialPrunedThrough >= 0)
        require(initial.size <= capacity)
        initial.forEach { record ->
            require(validId(record.requestId) && record.fingerprint.matches(Regex("[0-9a-f]{64}")))
            require(record.status in TERMINAL || record.status in ACTIVE)
            require(record.busyPolicy in POLICIES)
            require(!records.containsKey(record.requestId))
            records[record.requestId] = if (record.status in ACTIVE)
                record.copy(status = "unknown", reason = "process_restarted") else record
        }
        if (initial.any { it.status in ACTIVE }) write(records.values.toList())
    }
    fun claim(id: String, fingerprint: String, expiresAt: Long, busyPolicy: String = "skip",
              checkBusy: () -> String? = busyReason): Reply = synchronized(AnnouncementGate.monitor) {
        if (busyPolicy !in POLICIES) return@synchronized Reply(id, "failed", "invalid_policy")
        if (!validId(id) || !fingerprint.matches(Regex("[0-9a-f]{64}"))) return@synchronized Reply(id, "failed", "invalid_request")
        records[id]?.let { old ->
            if (old.fingerprint != fingerprint || old.expiresAt != expiresAt || old.busyPolicy != busyPolicy)
                return@synchronized Reply(id, "failed", "request_conflict")
            return@synchronized Reply(id, old.status, old.reason)
        }
        if (!healthy) return@synchronized Reply(id, "failed", "journal_unavailable")
        if (!prune()) return@synchronized Reply(id, "failed", "journal_unavailable")
        if (records.size >= capacity) return@synchronized Reply(id, "failed", "ledger_full")
        val remaining = expiresAt - wallNow()
        val reason = when {
            remaining <= 0 || expiresAt <= prunedThrough -> "expired"
            remaining > MAX_TTL_MS -> "invalid_expiry"
            else -> AnnouncementGate.claim(id, checkBusy)
        }
        val record = Record(id, fingerprint, expiresAt, if (reason == null) "accepted" else "skipped", reason ?: "", busyPolicy)
        val next = records.values.toMutableList().apply { add(record) }
        if (!write(next)) { AnnouncementGate.release(id); return@synchronized Reply(id, "failed", "journal_unavailable") }
        records[id] = record
        if (reason == null) deadline = monotonicNow() + remaining
        Reply(id, record.status, record.reason, reason == null)
    }
    fun policy(id: String): String? = synchronized(AnnouncementGate.monitor) { records[id]?.busyPolicy }
    fun status(id: String): Reply = synchronized(AnnouncementGate.monitor) {
        records[id]?.let { Reply(id, it.status, it.reason) } ?: Reply(id, "unknown", "not_found")
    }
    fun deadlineExpired(id: String): Boolean = synchronized(AnnouncementGate.monitor) {
        AnnouncementGate.owns(id) && (monotonicNow() >= deadline || wallNow() >= (records[id]?.expiresAt ?: 0))
    }
    fun playing(id: String): Reply = synchronized(AnnouncementGate.monitor) {
        val old = records[id] ?: return@synchronized Reply(id, "unknown", "not_found")
        if (!AnnouncementGate.owns(id) || old.status !in ACTIVE) return@synchronized Reply(id, old.status, old.reason)
        if (old.status == "playing") return@synchronized Reply(id, old.status)
        replace(old.copy(status = "playing"))
    }
    /** Call only after the owner has stopped/released its track. No unrelated player is touched. */
    fun finish(id: String, status: String, reason: String = "", releaseOwnership: Boolean = true): Reply = synchronized(AnnouncementGate.monitor) {
        require(status in TERMINAL)
        val old = records[id] ?: return@synchronized Reply(id, "unknown", "not_found")
        if (!AnnouncementGate.owns(id)) return@synchronized Reply(id, old.status, old.reason)
        val result = replace(old.copy(status = status, reason = reason))
        if (releaseOwnership) AnnouncementGate.release(id)
        result
    }
    private fun replace(record: Record): Reply {
        val next = records.values.map { if (it.requestId == record.requestId) record else it }
        if (!write(next)) {
            val unknown = record.copy(status = "unknown", reason = "journal_unavailable")
            records[record.requestId] = unknown
            return Reply(record.requestId, unknown.status, unknown.reason)
        }
        records[record.requestId] = record
        return Reply(record.requestId, record.status, record.reason)
    }
    private fun prunable(record: Record, now: Long): Boolean =
        record.status in TERMINAL && now > RETENTION_MS && record.expiresAt < now - RETENTION_MS
    private fun prune(): Boolean {
        val now = wallNow()
        val expired = records.values.filter { prunable(it, now) }
        if (expired.isEmpty()) return true
        val retired = expired.map { it.requestId }.toSet()
        val next = records.values.filterNot { it.requestId in retired }
        val nextFence = maxOf(prunedThrough, expired.maxOf { it.expiresAt })
        if (!write(next, nextFence)) return false
        records.clear()
        next.forEach { records[it.requestId] = it }
        prunedThrough = nextFence
        return true
    }
    private fun write(next: List<Record>, fence: Long = prunedThrough): Boolean =
        try { persist(next, fence); true } catch (_: Exception) { healthy = false; false }
    companion object {
        const val MAX_TTL_MS = 300_000L
        const val RETENTION_MS = 86_400_000L
        val POLICIES = setOf("skip", "duck_music")
        val ACTIVE = setOf("accepted", "playing")
        val TERMINAL = setOf("completed", "skipped", "failed", "stopped", "unknown")
        fun validId(id: String) = id.matches(Regex("announce-[0-9a-f]{32}-[0-9]{3}"))
    }
}

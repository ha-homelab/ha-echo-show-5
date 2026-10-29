// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

/** Durable idempotency ledger. It never evicts request IDs; full storage rejects new work. */
internal class AnnouncementLedger(
    initial: List<Record>,
    private val wallNow: () -> Long,
    private val monotonicNow: () -> Long,
    private val persist: (List<Record>) -> Unit,
    private val busyReason: () -> String?,
    private val capacity: Int = 2048,
) {
    data class Record(val requestId: String, val fingerprint: String, val expiresAt: Long,
                      val status: String, val reason: String = "")
    data class Reply(val requestId: String, val status: String, val reason: String = "", val fresh: Boolean = false)
    private val records = LinkedHashMap<String, Record>()
    private var deadline: Long = 0
    @Volatile var healthy: Boolean = true
        private set
    val current: String? get() = synchronized(AnnouncementGate.monitor) { records.values.lastOrNull { it.status in ACTIVE }?.requestId }
    init {
        require(initial.size <= capacity)
        initial.forEach { record ->
            require(validId(record.requestId) && record.fingerprint.matches(Regex("[0-9a-f]{64}")))
            require(record.status in TERMINAL || record.status in ACTIVE)
            require(!records.containsKey(record.requestId))
            records[record.requestId] = if (record.status in ACTIVE)
                record.copy(status = "unknown", reason = "process_restarted") else record
        }
        if (initial.any { it.status in ACTIVE }) write(records.values.toList())
    }
    fun claim(id: String, fingerprint: String, expiresAt: Long): Reply = synchronized(AnnouncementGate.monitor) {
        if (!validId(id) || !fingerprint.matches(Regex("[0-9a-f]{64}"))) return@synchronized Reply(id, "failed", "invalid_request")
        records[id]?.let { old ->
            if (old.fingerprint != fingerprint || old.expiresAt != expiresAt)
                return@synchronized Reply(id, "failed", "request_conflict")
            return@synchronized Reply(id, old.status, old.reason)
        }
        if (!healthy) return@synchronized Reply(id, "failed", "journal_unavailable")
        if (records.size >= capacity) return@synchronized Reply(id, "failed", "ledger_full")
        val remaining = expiresAt - wallNow()
        val reason = when {
            remaining <= 0 -> "expired"
            remaining > MAX_TTL_MS -> "invalid_expiry"
            else -> AnnouncementGate.claim(id, busyReason)
        }
        val record = Record(id, fingerprint, expiresAt, if (reason == null) "accepted" else "skipped", reason ?: "")
        val next = records.values.toMutableList().apply { add(record) }
        if (!write(next)) { AnnouncementGate.release(id); return@synchronized Reply(id, "failed", "journal_unavailable") }
        records[id] = record
        if (reason == null) deadline = monotonicNow() + remaining
        Reply(id, record.status, record.reason, reason == null)
    }
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
    private fun write(next: List<Record>): Boolean = try { persist(next); true } catch (_: Exception) { healthy = false; false }
    companion object {
        const val MAX_TTL_MS = 300_000L
        val ACTIVE = setOf("accepted", "playing")
        val TERMINAL = setOf("completed", "skipped", "failed", "stopped", "unknown")
        fun validId(id: String) = id.matches(Regex("announce-[0-9a-f]{32}-[0-9]{3}"))
    }
}

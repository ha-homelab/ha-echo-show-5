// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import android.content.Context
import android.os.SystemClock
import android.util.AtomicFile
import com.msp1974.vacompanion.satellite.Satellite
import com.msp1974.vacompanion.telephony.AudioLeaseRuntime
import com.msp1974.vacompanion.wyoming.SatelliteState
import com.msp1974.vacompanion.wyoming.WyomingPacket
import java.io.File
import java.util.concurrent.CopyOnWriteArraySet
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.json.*
import org.json.JSONArray
import org.json.JSONObject

/** Separate protocol; guarded audio is never injected into an Assist pipeline. */
object AnnouncementRuntime {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val mutex = Mutex()
    private val satellites = CopyOnWriteArraySet<Satellite>()
    private lateinit var environment: AnnouncementEnvironment
    private lateinit var context: Context
    private var ledger: AnnouncementLedger? = null
    @Volatile private var owner: Satellite? = null
    @Volatile private var ownerClient = ""
    @Volatile private var ownerId: String? = null
    private var audio: AnnouncementAudio? = null
    private var progress: PcmProgress? = null
    private var draining = false
    @Volatile private var quarantined = false
    private var watchdog: Job? = null
    private var lastData = 0L
    @Volatile private var abortRequest: Pair<String, String>? = null
    private fun abortReason(id: String): String? = abortRequest?.takeIf { it.first == id }?.second
    private val queuedBytes = AtomicLong()
    private val queue = Channel<Triple<Satellite, WyomingPacket, String>>(4096)

    @Synchronized fun initialize(value: Context) {
        if (::context.isInitialized) return
        context = value.applicationContext
        environment = AnnouncementEnvironment(context)
        val file = AtomicFile(File(context.filesDir, "announcement-ledger.json"))
        ledger = runCatching {
            val records = mutableListOf<AnnouncementLedger.Record>()
            var prunedThrough = 0L
            if (file.baseFile.exists() || File(file.baseFile.path + ".bak").exists()) {
                val raw = file.openRead().use { it.readBytes() }
                require(raw.size <= 1024 * 1024)
                val root = JSONObject(String(raw, Charsets.UTF_8))
                val version = root.getInt("version")
                require(version in 1..2)
                if (version == 2) prunedThrough = root.getLong("pruned_through_ms").also { require(it >= 0) }
                val items = root.getJSONArray("requests")
                require(items.length() <= 2048)
                for (index in 0 until items.length()) {
                    val row = items.getJSONObject(index)
                    records.add(AnnouncementLedger.Record(row.getString("request_id"), row.getString("fingerprint"),
                        row.getLong("expires_at_ms"), row.getString("status"), row.optString("reason")))
                }
            }
            AnnouncementLedger(records, System::currentTimeMillis, SystemClock::elapsedRealtime, { rows, fence ->
                val array = JSONArray()
                rows.forEach { row -> array.put(JSONObject().put("request_id", row.requestId)
                    .put("fingerprint", row.fingerprint).put("expires_at_ms", row.expiresAt)
                    .put("status", row.status).put("reason", row.reason)) }
                val bytes = JSONObject().put("version", 2).put("pruned_through_ms", fence)
                    .put("requests", array).toString().toByteArray(Charsets.UTF_8)
                require(bytes.size <= 1024 * 1024)
                val stream = file.startWrite()
                try { stream.write(bytes); file.finishWrite(stream) }
                catch (error: Exception) { file.failWrite(stream); throw error }
            }, ::busyReason, initialPrunedThrough = prunedThrough)
        }.getOrNull()
        scope.launch {
            for ((satellite, packet, client) in queue) {
                queuedBytes.addAndGet(-packet.payload.size.toLong())
                try { handleLocked(satellite, packet, client) }
                catch (_: Exception) { mutex.withLock {
                    if (ownerId == packet.getProp("request_id") && owner === satellite && ownerClient == client) finishLocked("failed", "invalid_packet")
                    else reply(satellite, client, packet.getProp("request_id"), packet.getProp("op"), "failed", "invalid_packet")
                } }
            }
        }
    }
    fun attach(satellite: Satellite) { initialize(satellite.context); satellites.add(satellite) }
    fun detach(satellite: Satellite) {
        satellites.remove(satellite)
        val expected = ownerId
        val client = ownerClient
        if (expected != null && owner === satellite) {
            abortRequest = expected to "connection_lost"
            scope.launch { mutex.withLock {
                if (owner === satellite && ownerId == expected && ownerClient == client) finishLocked("unknown", "connection_lost")
            } }
        }
    }
    /** Called before SIP acquisition; only the currently owned announcement is stopped. */
    suspend fun preemptForSip() {
        preemptAnnouncementOwner(mutex, { ownerId },
            { current -> abortRequest = current to "sip_preempted" },
            { finishLocked("stopped", "sip_preempted") })
    }
    fun stopByWakeWord(satellite: Satellite) {
        val expected = ownerId ?: return
        if (owner !== satellite) return
        abortRequest = expected to "local_stop"
        scope.launch { mutex.withLock { if (ownerId == expected && owner === satellite) finishLocked("stopped", "local_stop") } }
    }
    private fun busyReason(): String? = when {
        AudioLeaseRuntime.reserved -> "sip_busy"
        satellites.none { it.state == SatelliteState.RUNNING } -> "satellite_unavailable"
        satellites.any { it.config.isMuted || it.config.doNotDisturb } -> "muted_or_do_not_disturb"
        satellites.any { it.isBusyForAudioLease() } -> "assist_or_media_busy"
        else -> environment.reason()
    }
    private fun ready(): Boolean = !quarantined && ledger?.canAcceptNew == true && environment.compatibleSip() && environment.usageAccess()
    suspend fun handle(satellite: Satellite, packet: WyomingPacket, sourceClient: String) {
        if (packet.payload.size > 16384) return
        // Control operations bypass bounded PCM queue. A full queue fails rather than blocking cancellation.
        if (packet.getProp("op") == "cancel" && AnnouncementGate.owns(packet.getProp("request_id")) && owner === satellite && ownerClient == sourceClient) abortRequest = packet.getProp("request_id") to "cancelled"
        if (packet.getProp("op") in setOf("cancel", "status", "capabilities")) handleLocked(satellite, packet, sourceClient)
        else if (queuedBytes.addAndGet(packet.payload.size.toLong()) > PcmProgress.MAX_BYTES || queue.trySend(Triple(satellite, packet, sourceClient)).isFailure) {
            queuedBytes.addAndGet(-packet.payload.size.toLong())
            mutex.withLock {
                if (packet.getProp("request_id") == ownerId && owner === satellite && ownerClient == sourceClient)
                    finishLocked("failed", "input_overflow")
            }
        }
    }
    private suspend fun handleLocked(satellite: Satellite, packet: WyomingPacket, sourceClient: String) = mutex.withLock {
        val op = packet.getProp("op")
        val id = packet.getProp("request_id")
        if (!AnnouncementLedger.validId(id)) return@withLock
        if (sourceClient != satellite.clientId) { reply(satellite, sourceClient, id, op, "failed", "not_owner"); return@withLock }
        if (op == "capabilities") {
            satellite.sendSatelliteMessage(sourceClient, "guarded-announce-result", buildJsonObject {
                put("request_id", id); put("op", op); put("status", "accepted"); put("protocol", "cisco-announcement-v1")
                put("protocol_version", 1); put("supported", ready())
                put("atomic_idle_guard", ready()); put("dedup", ledger?.healthy == true)
                put("owned_cancel", true); put("honest_completion", true); put("deadline_enforced", true)
                put("guard_scope", "coordinated_vaca_sip"); put("external_busy_policy", "observe_and_abort")
                put("global_android_exclusion", false)
            })
            return@withLock
        }
        val book = ledger
        if (book == null) { reply(satellite, sourceClient, id, op, "failed", "journal_unavailable"); return@withLock }
        if (op == "status" || quarantined) { reply(satellite, sourceClient, book.status(id), op); return@withLock }
        if (op == "claim") {
            val seconds = packet.data["expires_at"]?.jsonPrimitive?.longOrNull
            if (seconds == null || seconds <= 0 || seconds > Long.MAX_VALUE / 1000) {
                reply(satellite, sourceClient, id, op, "failed", "invalid_expiry"); return@withLock
            }
            val result = book.claim(id, packet.getProp("payload_fingerprint"), seconds * 1000)
            if (result.fresh) {
                owner = satellite; ownerId = id; ownerClient = sourceClient; lastData = SystemClock.elapsedRealtime(); abortRequest = null
                progress = PcmProgress(); draining = false
                watchdog = scope.launch {
                    while (isActive) {
                        delay(100)
                        if (book.deadlineExpired(id)) abortRequest = id to "expired"
                        mutex.withLock {
                            if (!AnnouncementGate.owns(id)) return@launch
                            val reason = when {
                                abortReason(id) != null -> abortReason(id)
                                SystemClock.elapsedRealtime() - lastData > 15000 && !draining -> "input_timeout"
                                satellite.config.isMuted || satellite.config.doNotDisturb -> "muted_or_do_not_disturb"
                                else -> environment.reason(ownPlayback = audio != null)
                            }
                            if (reason != null) { finishLocked("stopped", reason); return@launch }
                        }
                    }
                }
            }
            reply(satellite, sourceClient, result, op)
            return@withLock
        }
        if (!AnnouncementGate.owns(id) || owner !== satellite || ownerClient != sourceClient) {
            reply(satellite, sourceClient, book.status(id), op)
            return@withLock
        }
        if (op == "cancel") { finishLocked("stopped", "cancelled", op); return@withLock }
        if (book.deadlineExpired(id)) { finishLocked("stopped", "expired", op); return@withLock }
        try {
            when (op) {
                "audio-start" -> {
                    require(audio == null && !draining) { "duplicate_start" }
                    require(packet.getProp("rate") == "22050" && packet.getProp("width") == "2" && packet.getProp("channels") == "1") { "audio_format" }
                    environment.reason()?.let { throw IllegalStateException(it) }
                    val player = AnnouncementAudio(context) {
                        abortRequest = id to "audio_focus_lost"
                        scope.launch { mutex.withLock { if (AnnouncementGate.owns(id)) finishLocked("stopped", "audio_focus_lost") } }
                    }
                    audio = player
                    player.start()
                    lastData = SystemClock.elapsedRealtime()
                }
                "audio-chunk" -> {
                    check(!draining) { "after_end" }
                    val sink = checkNotNull(audio) { "not_started" }
                    val pcm = checkNotNull(progress)
                    val sequence = packet.data["sequence"]?.jsonPrimitive?.longOrNull ?: -1
                    pcm.begin(sequence, packet.payload.size)
                    var offset = 0
                    val writeDeadline = SystemClock.elapsedRealtime() + 2000
                    while (offset < packet.payload.size) {
                        if (abortReason(id) != null) { finishLocked("stopped", abortReason(id)!!); return@withLock }
                        check(SystemClock.elapsedRealtime() < writeDeadline && !book.deadlineExpired(id)) { "write_timeout" }
                        val wrote = sink.write(packet.payload, offset)
                        check(wrote >= 0) { "write_failed" }
                        if (wrote == 0) { delay(5); continue }
                        pcm.wrote(wrote); offset += wrote
                    }
                    lastData = SystemClock.elapsedRealtime()
                    val result = book.playing(id)
                    if (result.status != "playing") { finishLocked("unknown", "journal_unavailable"); return@withLock }
                    if (sequence == 0L) reply(satellite, sourceClient, result, "event")
                }
                "audio-stop" -> {
                    check(!draining) { "duplicate_end" }
                    val pcm = checkNotNull(progress)
                    check(pcm.canFinish()) { "empty_audio" }
                    val sink = checkNotNull(audio)
                    draining = true
                    scope.launch {
                        while (isActive) {
                            delay(10)
                            val done = mutex.withLock {
                                if (!AnnouncementGate.owns(id)) return@withLock true
                                try {
                                    if (abortReason(id) != null) { finishLocked("stopped", abortReason(id)!!); true }
                                    else if (book.deadlineExpired(id)) { finishLocked("stopped", "expired"); true }
                                    else if (pcm.drained(sink.renderedFrames())) { finishLocked("completed", "drained"); true }
                                    else false
                                } catch (_: Exception) { finishLocked("failed", "drain_failed"); true }
                            }
                            if (done) break
                        }
                    }
                }
                else -> reply(satellite, sourceClient, id, op, "failed", "unknown_operation")
            }
        } catch (_: Exception) { finishLocked("failed", "audio_failed", op) }
    }

    private fun finishLocked(status: String, reason: String, op: String = "event") {
        val id = ownerId ?: return
        if (quarantined) return
        val target = owner
        val source = ownerClient
        watchdog?.cancel(); watchdog = null
        var finalStatus = status
        var finalReason = reason
        try { audio?.close() } catch (_: Exception) {
            finalStatus = "unknown"; finalReason = "release_failed"; quarantined = true
        }
        if (!quarantined) { audio = null; progress = null; draining = false; owner = null; ownerId = null; ownerClient = "" }
        val result = ledger!!.finish(id, finalStatus, finalReason, releaseOwnership = !quarantined)
        if (target != null) reply(target, source, result, op)
    }
    private fun reply(satellite: Satellite, source: String, result: AnnouncementLedger.Reply, op: String) {
        if (op == "claim") {
            satellite.sendSatelliteMessage(source, "guarded-announce-result", buildJsonObject {
                put("request_id", result.requestId); put("op", op); put("status", result.status)
                put("reason", result.reason); put("deduplicated", !result.fresh)
            })
        } else reply(satellite, source, result.requestId, op, result.status, result.reason)
    }
    private fun reply(satellite: Satellite, source: String, id: String, op: String, status: String, reason: String) {
        satellite.sendSatelliteMessage(source, "guarded-announce-result", buildJsonObject {
            put("request_id", id); put("op", op); put("status", status); put("reason", reason)
        })
    }
}

package com.msp1974.vacompanion.nearest

import android.content.Context
import android.os.SystemClock
import android.util.AtomicFile
import com.msp1974.vacompanion.wakeword.WakeWordEngineProvider
import kotlinx.coroutines.*
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.atomic.AtomicLong

/** One existing capture feeds measurements and bounded RAM history; no additional recorder. */
object NearestAudioTap {
    private val owner = AtomicReference<NearestRuntime?>()
    private val sequence = AtomicLong()
    internal fun attach(runtime: NearestRuntime) { owner.set(runtime) }
    internal fun detach(runtime: NearestRuntime) { owner.compareAndSet(runtime, null) }
    fun raw(samples: ShortArray, suppressed: Boolean) { if (!suppressed) owner.get()?.raw(samples) }
    fun processed(samples: ShortArray): Long {
        val id = sequence.incrementAndGet(); owner.get()?.processed(samples, id); return id
    }
}

class NearestRuntime(
    private val context: Context, private val parentScope: CoroutineScope,
    private val canAnswer: () -> Boolean,
    private val captureAllowed: () -> Boolean,
    private val open: suspend (WakeWordEngineProvider.WakeWordDetection) -> Unit,
) {
    private val lock = Any()
    private val statusLock = Any()
    private val lifecycle = AtomicLong()
    private val initializer = Mutex()
    private val guard = WakeTurnGuard()
    private val meter = StandoutScore()
    private val history = PrerollBuffer()
    private var config = NearestConfig()
    private var election = NearestElection()
    private var scope: CoroutineScope? = null
    private var transport: NearestTransport? = null
    private var task: Job? = null
    private var replayFrom: Long? = null
    private var replayUnattenuatedUntil = 0L
    private var result = "stopped"
    private var modelId = ""
    private var localScore = 0.0
    private var answeredProof = false
    private val verifiedPeers = linkedSetOf<String>()
    private val reload: () -> Unit = {
        val revision = lifecycle.get()
        parentScope.launch { reconfigure(revision) }; Unit
    }

    suspend fun start() { reconfigure(null) }

    private suspend fun reconfigure(expected: Long?) {
        // Reserve synchronously before dispatch: stop invalidates queued and in-flight reloads.
        val revision = synchronized(lock) {
            if (expected != null && lifecycle.get() != expected) return
            stop()
            lifecycle.get()
        }
        withContext(Dispatchers.Default) {
            initializer.withLock {
                if (lifecycle.get() != revision) return@withLock
                val loaded = NearestSettings.read(context)
                var candidate: NearestTransport? = null
                var nextResult = "disabled"
                if (loaded.enabled) {
                    try {
                        candidate = NearestTransport(context, loaded) { claim ->
                            synchronized(lock) {
                                if (lifecycle.get() != revision) false
                                else {
                                    if (result == "electing" && claim.word == modelId && verifiedPeers.size < 32)
                                        verifiedPeers.add(claim.from)
                                    election.receive(claim, SystemClock.elapsedRealtime())
                                }
                            }
                        }
                        candidate.start()
                        nextResult = "ready"
                    } catch (_: Exception) {
                        candidate?.close(); candidate = null; nextResult = "network_unavailable"
                    }
                }
                val active = currentCoroutineContext().isActive
                synchronized(lock) {
                    if (lifecycle.get() != revision || !active) {
                        candidate?.close(); return@withLock
                    }
                    config = loaded; transport = candidate; result = nextResult
                    scope = CoroutineScope(parentScope.coroutineContext + SupervisorJob(parentScope.coroutineContext[Job]))
                    NearestSettings.listen(reload)
                    if (candidate != null) NearestAudioTap.attach(this@NearestRuntime)
                }
                status()
                scope?.launch { while (isActive) { delay(30_000); status() } }
            }
        }
    }

    /** Returns immediately to the PCM collection; network I/O never runs on its coroutine. */
    fun wake(detection: WakeWordEngineProvider.WakeWordDetection) {
        if (!canAnswer()) return
        val token = guard.begin() ?: return
        val worker = scope ?: parentScope
        val started = SystemClock.elapsedRealtime()
        synchronized(lock) {
            verifiedPeers.clear(); answeredProof = false; modelId = detection.wakeWordId
            localScore = NearestElection.adjustedScore(meter.score(), config.offsetDb)
            result = "electing"
        }
        val network = transport
        val peers = network?.peers().orEmpty()
        if (!config.enabled || network == null || peers.isEmpty()) {
            task = worker.launch {
                try {
                    result = "uncoordinated"; status()
                    if (guard.current(token) && canAnswer()) open(detection)
                }
                finally { guard.finish(token) }
            }
            return
        }
        val pending = synchronized(lock) {
            election.begin(NearestClaim(config.name, NearestWire.newTurn(), detection.wakeWordId,
                localScore), started, config.windowMs)
        }
        peers.forEach { peer -> worker.launch(Dispatchers.IO) {
            if (network.post(peer, pending.claim) && guard.current(token))
                synchronized(lock) { answeredProof = true; verifiedPeers.add(peer.name); election.markAnsweredElsewhere(pending) }
        } }
        task = worker.launch {
            delay(config.windowMs)
            if (!guard.current(token)) return@launch
            val decision = synchronized(lock) { election.decide(pending, SystemClock.elapsedRealtime(), canAnswer()) }
            if (decision == NearestElection.Decision.START && guard.current(token) && canAnswer()) {
                synchronized(lock) { replayFrom = started - 80; replayUnattenuatedUntil = SystemClock.elapsedRealtime() }
                try { result = synchronized(lock) { if (verifiedPeers.isEmpty()) "unconfirmed_local" else "answering" }; status(); if (guard.current(token) && canAnswer()) open(detection) }
                finally { guard.finish(token) }
            } else { guard.finish(token); synchronized(lock) { clearReplay() }; result = "yielded"; status() }
        }
    }

    internal fun raw(samples: ShortArray) = synchronized(lock) { if (config.enabled && captureAllowed()) meter.add(samples) }
    internal fun processed(samples: ShortArray, sequence: Long) = synchronized(lock) {
        if (config.enabled && captureAllowed()) history.add(samples, SystemClock.elapsedRealtime(), System.currentTimeMillis(), sequence)
    }

    /** Drained once, immediately before the first live frame of the winning pipeline. */
    fun takeReplay(liveSequence: Long): List<WakeWordEngineProvider.AudioResult.Audio> = synchronized(lock) {
        val from = replayFrom ?: return@synchronized emptyList()
        replayFrom = null
        if (liveSequence <= 0) return@synchronized emptyList()
        history.beforeSequence(from, liveSequence).map {
            WakeWordEngineProvider.AudioResult.Audio(it.pcm, it.wallMs, it.monotonicMs <= replayUnattenuatedUntil, it.sequence)
        }
    }

    fun cancel() {
        guard.cancel(); task?.cancel(); task = null
        synchronized(lock) { election.cancel(); history.clear(); meter.reset(); clearReplay() }
    }
    private fun clearReplay() { replayFrom = null; replayUnattenuatedUntil = 0L }
    fun stop() = synchronized(lock) {
        lifecycle.incrementAndGet()
        NearestSettings.unlisten(reload); NearestAudioTap.detach(this); cancel()
        scope?.cancel(); scope = null
        transport?.close(); transport = null
        synchronized(lock) { election = NearestElection() }
        result = "stopped"
    }
    private fun status() = synchronized(statusLock) {
        // Fixed metadata only. No request headers, house word, PCM or spoken text.
        val d = JSONObject().put("schema", 1).put("enabled", config.enabled).put("name", config.name)
            .put("state", result).put("window_ms", config.windowMs).put("offset_db", config.offsetDb)
            .put("network_state", transport?.networkState() ?: "off")
            .put("local_score", localScore).put("verified_claim_peers", JSONArray(synchronized(lock) { verifiedPeers.toList() }))
            .put("verified_answered_proof", answeredProof)
            .put("peers", JSONArray(transport?.peers()?.map { it.name }.orEmpty()))
            .put("updated_at_ms", System.currentTimeMillis())
        runCatching {
            val file = AtomicFile(File(context.filesDir, "nearest-status.json"))
            val stream = file.startWrite()
            try { stream.write(d.toString().toByteArray()); file.finishWrite(stream) }
            catch (e: Exception) { file.failWrite(stream); throw e }
        }
    }
}

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
    private val open: suspend (WakeWordEngineProvider.WakeWordDetection, Long) -> Unit,
) {
    private val lock = Any()
    private val statusLock = Any()
    private val lifecycle = NearestLifecycle()
    private val initializer = Mutex()
    private val guard = WakeTurnGuard()
    private val meter = StandoutScore()
    private val history = PrerollBuffer()
    private var config = NearestConfig()
    private var election = NearestElection()
    private var scope: CoroutineScope? = null
    private var transport: NearestTransport? = null
    private var task: Job? = null
    private val replay = NearestReplay()
    private var configured = false
    private var readiness = "disabled"
    private var result = "stopped"
    private var modelId = ""
    private var localScore = 0.0
    private var answeredProof = false
    private val verifiedPeers = linkedSetOf<String>()
    private val reload: () -> Unit = {
        val revision = synchronized(lock) { lifecycle.revision }
        parentScope.launch { reconfigure(revision) }; Unit
    }

    suspend fun start() { reconfigure(null) }

    private suspend fun reconfigure(expected: Long?) {
        val revision = synchronized(lock) {
            val next = if (expected == null) lifecycle.start() else lifecycle.reload(expected) ?: return
            // Stay inactive while configuration is read or a replacement is initialized.
            cancel()
            NearestAudioTap.detach(this)
            if (scope == null) {
                scope = CoroutineScope(parentScope.coroutineContext + SupervisorJob(parentScope.coroutineContext[Job]))
                scope!!.launch { while (isActive) { delay(30_000); status() } }
            }
            NearestSettings.listen(reload)
            next
        }
        withContext(Dispatchers.Default) {
            initializer.withLock {
                if (!synchronized(lock) { lifecycle.current(revision) }) return@withLock
                val loaded = NearestSettings.read(context)
                val unchanged = synchronized(lock) {
                    if (!lifecycle.current(revision)) return@withLock
                    configured && loaded.sameConfiguration(config)
                }
                if (unchanged) {
                    synchronized(lock) {
                        if (lifecycle.activate(revision)) {
                            result = readiness
                            if (transport != null) NearestAudioTap.attach(this@NearestRuntime)
                        }
                    }
                    status()
                    return@withLock
                }
                val generation = synchronized(lock) {
                    if (!lifecycle.current(revision)) return@withLock
                    val generation = lifecycle.replaceTransport()
                    transport?.close(); transport = null
                    configured = false
                    election = NearestElection()
                    generation
                }
                var candidate: NearestTransport? = null
                var adopted = false
                try {
                    var nextResult = "disabled"
                    if (loaded.enabled) {
                        try {
                            candidate = NearestTransport(context, loaded) { claim ->
                                synchronized(lock) {
                                    if (!lifecycle.acceptsClaim(generation) || !captureAllowed()) false
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
                    val running = currentCoroutineContext().isActive
                    synchronized(lock) {
                        if (!running || !lifecycle.activate(revision)) return@withLock
                        config = loaded; transport = candidate; result = nextResult; readiness = nextResult
                        configured = !loaded.enabled || candidate != null
                        adopted = true
                        if (candidate != null) NearestAudioTap.attach(this@NearestRuntime)
                    }
                    status()
                } finally {
                    if (!adopted) candidate?.close()
                }
            }
        }
    }

    /** Returns immediately to the PCM collection; network I/O never runs on its coroutine. */
    fun wake(detection: WakeWordEngineProvider.WakeWordDetection) {
        synchronized(lock) {
            if (!lifecycle.active || !nearestWakeAllowed(config.enabled, canAnswer, captureAllowed)) return
            val token = guard.begin() ?: return
            val worker = scope ?: run { guard.finish(token); return }
            val started = SystemClock.elapsedRealtime()
            replay.clear()
            verifiedPeers.clear(); answeredProof = false; modelId = detection.wakeWordId
            localScore = NearestElection.adjustedScore(meter.score(), config.offsetDb)
            result = "electing"
            val network = transport
            val peers = network?.peers().orEmpty()
            if (!config.enabled || network == null || peers.isEmpty()) {
                task = worker.launch {
                    try {
                        val admitted = synchronized(lock) {
                            if (!lifecycle.active || !guard.current(token)) false
                            else { result = "uncoordinated"; true }
                        }
                        if (admitted) {
                            status()
                            openTurn(token, detection, coordinated = false)
                        }
                    } finally { synchronized(lock) { guard.finish(token) } }
                }
                return
            }
            val pending = election.begin(NearestClaim(config.name, NearestWire.newTurn(), detection.wakeWordId,
                localScore), started, config.windowMs)
            val window = config.windowMs
            peers.forEach { peer -> worker.launch(Dispatchers.IO) {
                val current = synchronized(lock) { lifecycle.active && guard.current(token) }
                if (current && network.post(peer, pending.claim)) synchronized(lock) {
                    if (lifecycle.active && guard.current(token)) {
                        answeredProof = true; verifiedPeers.add(peer.name); election.markAnsweredElsewhere(pending)
                    }
                }
            } }
            task = worker.launch {
                try {
                    delay(window)
                    val admitted = synchronized(lock) {
                        if (!lifecycle.active || !guard.current(token)) return@launch
                        if (election.decide(pending, SystemClock.elapsedRealtime(), canAnswer()) == NearestElection.Decision.START) {
                            replay.arm(token, started - 80, SystemClock.elapsedRealtime())
                            result = if (verifiedPeers.isEmpty()) "unconfirmed_local" else "answering"
                            true
                        } else { replay.clear(); result = "yielded"; false }
                    }
                    status()
                    if (admitted) openTurn(token, detection, coordinated = true)
                } finally { synchronized(lock) { guard.finish(token) } }
            }
        }
    }

    private suspend fun openTurn(token: Long, detection: WakeWordEngineProvider.WakeWordDetection, coordinated: Boolean) {
        var completed = false
        try {
            val admitted = synchronized(lock) {
                lifecycle.active && guard.current(token) &&
                    (if (coordinated) canAnswer() else nearestWakeAllowed(config.enabled, canAnswer, captureAllowed))
            }
            if (admitted) { open(detection, token); completed = true }
        } finally { synchronized(lock) { replay.finishOpen(token, completed) } }
    }

    internal fun raw(samples: ShortArray) = synchronized(lock) { if (lifecycle.active && config.enabled && captureAllowed()) meter.add(samples) }
    internal fun processed(samples: ShortArray, sequence: Long) = synchronized(lock) {
        if (lifecycle.active && config.enabled && captureAllowed()) history.add(samples, SystemClock.elapsedRealtime(), System.currentTimeMillis(), sequence)
    }

    fun bindReplay(turn: Long?, pipeline: Any) = synchronized(lock) { replay.bind(turn, pipeline) }
    fun releaseReplay(pipeline: Any) = synchronized(lock) { replay.release(pipeline) }

    /** Only the pipeline created by the winning turn can drain its history, once. */
    fun takeReplay(pipeline: Any, liveSequence: Long): List<WakeWordEngineProvider.AudioResult.Audio> = synchronized(lock) {
        val window = replay.take(pipeline) ?: return@synchronized emptyList()
        if (!lifecycle.active || !captureAllowed() || liveSequence <= 0) return@synchronized emptyList()
        history.beforeSequence(window.from, liveSequence).map {
            WakeWordEngineProvider.AudioResult.Audio(it.pcm, it.wallMs, it.monotonicMs <= window.unattenuatedUntil, it.sequence)
        }
    }

    fun cancel() = synchronized(lock) {
        guard.cancel(); task?.cancel(); task = null
        election.cancel(); history.clear(); meter.reset(); replay.clear()
    }

    /** Wake listener pause: keep authenticated peers and discovery, but refuse all elections. */
    fun pause() = synchronized(lock) {
        lifecycle.pause()
        NearestAudioTap.detach(this); cancel()
        election = NearestElection()
        result = "inactive"
    }

    /** Satellite teardown: release the retained transport and listener. */
    fun stop() = synchronized(lock) {
        pause()
        NearestSettings.unlisten(reload)
        scope?.cancel(); scope = null
        transport?.close(); transport = null
        lifecycle.replaceTransport(); configured = false
        result = "stopped"
    }
    private fun status() {
        // Fixed metadata only. No request headers, house word, PCM or spoken text.
        val d = synchronized(lock) { JSONObject().put("schema", 1).put("enabled", config.enabled).put("name", config.name)
            .put("active", lifecycle.active).put("state", result).put("window_ms", config.windowMs).put("offset_db", config.offsetDb)
            .put("network_state", transport?.networkState() ?: "off")
            .put("local_score", localScore).put("verified_claim_peers", JSONArray(verifiedPeers.toList()))
            .put("verified_answered_proof", answeredProof)
            .put("peers", JSONArray(transport?.peers()?.map { it.name }.orEmpty()))
            .put("updated_at_ms", System.currentTimeMillis()) }
        synchronized(statusLock) { runCatching {
            val file = AtomicFile(File(context.filesDir, "nearest-status.json"))
            val stream = file.startWrite()
            try { stream.write(d.toString().toByteArray()); file.finishWrite(stream) }
            catch (e: Exception) { file.failWrite(stream); throw e }
        } }
    }
}

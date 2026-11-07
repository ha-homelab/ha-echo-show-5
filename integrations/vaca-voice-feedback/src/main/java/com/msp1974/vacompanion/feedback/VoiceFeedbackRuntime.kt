package com.msp1974.vacompanion.feedback

import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** A phase indicator, never an estimate of microphone amplitude. */
enum class FeedbackPhase(val label: String) {
    HIDDEN(""), LISTENING("Listening"), THINKING("Thinking"), SPEAKING("Speaking")
}

data class FeedbackState(val phase: FeedbackPhase = FeedbackPhase.HIDDEN)

internal fun interface FeedbackCancellation { fun cancel() }

/** Identity ownership prevents an old pipeline's callback from hiding a newer turn. */
internal class VoiceFeedbackController(
    private val nowMs: () -> Long,
    private val schedule: (Long, () -> Unit) -> FeedbackCancellation
) {
    private val mutableState = MutableStateFlow(FeedbackState())
    val state: StateFlow<FeedbackState> = mutableState.asStateFlow()
    private var owner: Any? = null
    private var startedAt = 0L
    private var revision = 0L
    private var deadline: FeedbackCancellation? = null

    @Synchronized
    fun begin(turn: Any) {
        // Admission can be reported twice; it must not extend a stuck session.
        if (owner === turn) return
        owner = turn
        startedAt = nowMs()
        publish(FeedbackPhase.LISTENING)
    }

    @Synchronized
    fun owns(turn: Any): Boolean = owner === turn

    @Synchronized
    fun update(turn: Any, stage: String) {
        if (owner !== turn) return
        val next = when (stage) {
            "LISTENING", "VOICE_STARTED" -> FeedbackPhase.LISTENING
            "VOICE_STOPPED", "AWAITING_RESPONSE", "AWAITING_TTS", "STARTING_TTS" -> FeedbackPhase.THINKING
            "STREAMING_TTS" -> FeedbackPhase.SPEAKING
            "COMPLETED_TTS", "ENDED" -> FeedbackPhase.HIDDEN
            else -> return
        }
        if (next == FeedbackPhase.HIDDEN) { clearOwned(); return }
        // Late/duplicate pipeline events cannot rewind feedback or renew its lease.
        if (next.ordinal <= mutableState.value.phase.ordinal) return
        publish(next)
    }

    @Synchronized
    fun clear(turn: Any) { if (owner === turn) clearOwned() }

    @Synchronized
    fun clearAll() { clearOwned() }

    private fun publish(phase: FeedbackPhase) {
        deadline?.cancel()
        val currentOwner = owner ?: return
        val currentRevision = ++revision
        val elapsed = (nowMs() - startedAt).coerceAtLeast(0L)
        val lease = minOf(leaseMs(phase), (MAX_TURN_MS - elapsed).coerceAtLeast(0L))
        if (lease == 0L) { clearOwned(); return }
        mutableState.value = FeedbackState(phase)
        deadline = schedule(lease) {
            synchronized(this) {
                // Cancellation can race execution; validate identity AND phase generation.
                if (owner === currentOwner && revision == currentRevision) clearOwned()
            }
        }
    }

    private fun clearOwned() {
        ++revision
        deadline?.cancel()
        deadline = null
        owner = null
        mutableState.value = FeedbackState()
    }

    companion object {
        const val LISTENING_MS = 45_000L
        const val THINKING_MS = 120_000L
        const val SPEAKING_MS = 300_000L
        const val MAX_TURN_MS = 420_000L
        fun leaseMs(phase: FeedbackPhase): Long = when (phase) {
            FeedbackPhase.LISTENING -> LISTENING_MS
            FeedbackPhase.THINKING -> THINKING_MS
            FeedbackPhase.SPEAKING -> SPEAKING_MS
            FeedbackPhase.HIDDEN -> 0L
        }
    }
}

/** Local, credential-free UI state. Deadlines only clear this visual, never audio. */
object VoiceFeedbackRuntime {
    private val deadlines = Executors.newSingleThreadScheduledExecutor { runnable ->
        Thread(runnable, "voice-feedback-expiry").apply { isDaemon = true }
    }
    private val controller = VoiceFeedbackController(
        nowMs = { TimeUnit.NANOSECONDS.toMillis(System.nanoTime()) },
        schedule = { delay, action ->
            val future = deadlines.schedule({ action() }, delay, TimeUnit.MILLISECONDS)
            FeedbackCancellation { future.cancel(false) }
        }
    )
    val state: StateFlow<FeedbackState> = controller.state
    fun begin(owner: Any) = controller.begin(owner)
    fun owns(owner: Any): Boolean = controller.owns(owner)
    fun update(owner: Any, stage: String) = controller.update(owner, stage)
    fun clear(owner: Any) = controller.clear(owner)
    fun clearAll() = controller.clearAll()
}

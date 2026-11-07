package com.msp1974.vacompanion.feedback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class VoiceFeedbackRuntimeTest {
    private class Clock {
        var now = 0L
        data class Alarm(val at: Long, val action: () -> Unit, var cancelled: Boolean = false)
        val alarms = mutableListOf<Alarm>()
        val controller = VoiceFeedbackController({ now }) { delay, action ->
            val alarm = Alarm(now + delay, action)
            alarms.add(alarm)
            FeedbackCancellation { alarm.cancelled = true }
        }
        fun phase() = controller.state.value.phase
        fun advance(delta: Long) {
            now += delta
            val due = alarms.filter { !it.cancelled && it.at <= now }
            due.forEach { it.cancelled = true; it.action() }
        }
    }

    @Test fun idleAndUnacceptedEventsStayInvisible() {
        val clock = Clock()
        val owner = Any()
        clock.controller.update(owner, "LISTENING")
        clock.controller.update(owner, "STREAMING_TTS")
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
        assertFalse(clock.controller.owns(owner))
        assertTrue(clock.alarms.isEmpty())
    }

    @Test fun acceptedTurnShowsListeningThenThinkingThenSpeakingThenNothing() {
        val clock = Clock()
        val owner = Any()
        clock.controller.begin(owner)
        assertEquals(FeedbackPhase.LISTENING, clock.phase())
        clock.controller.update(owner, "VOICE_STOPPED")
        assertEquals(FeedbackPhase.THINKING, clock.phase())
        clock.controller.update(owner, "STREAMING_TTS")
        assertEquals(FeedbackPhase.SPEAKING, clock.phase())
        clock.controller.update(owner, "COMPLETED_TTS")
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
        assertFalse(clock.controller.owns(owner))
    }

    @Test fun ownershipUsesIdentityEvenForEqualObjects() {
        data class Owner(val name: String)
        val clock = Clock()
        val accepted = Owner("same")
        val foreign = Owner("same")
        clock.controller.begin(accepted)
        assertFalse(clock.controller.owns(foreign))
        clock.controller.update(foreign, "STREAMING_TTS")
        clock.controller.clear(foreign)
        assertEquals(FeedbackPhase.LISTENING, clock.phase())
        assertTrue(clock.controller.owns(accepted))
    }

    @Test fun oldCallbacksCannotClearOrUpdateANewerOwner() {
        val clock = Clock()
        val old = Any()
        val current = Any()
        clock.controller.begin(old)
        val staleDeadline = clock.alarms.last()
        clock.controller.begin(current)
        clock.controller.clear(old)
        clock.controller.update(old, "ENDED")
        clock.controller.update(old, "STREAMING_TTS")
        staleDeadline.action() // Model cancellation racing an already dispatched callback.
        assertEquals(FeedbackPhase.LISTENING, clock.phase())
        assertTrue(clock.controller.owns(current))
    }

    @Test fun oldPhaseDeadlineCannotClearTheSameOwnersNewPhase() {
        val clock = Clock()
        val owner = Any()
        clock.controller.begin(owner)
        val listeningDeadline = clock.alarms.last()
        clock.controller.update(owner, "AWAITING_RESPONSE")
        listeningDeadline.action()
        assertEquals(FeedbackPhase.THINKING, clock.phase())
        clock.controller.update(owner, "STREAMING_TTS")
        val speakingDeadline = clock.alarms.last()
        clock.alarms[1].action()
        assertEquals(FeedbackPhase.SPEAKING, clock.phase())
        speakingDeadline.action()
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
    }

    @Test fun duplicateAndDelayedStagesNeverRewindOrExtendFeedback() {
        val clock = Clock()
        val owner = Any()
        clock.controller.begin(owner)
        clock.advance(10_000)
        clock.controller.begin(owner)
        clock.controller.update(owner, "VOICE_STARTED")
        assertEquals(1, clock.alarms.size)
        clock.controller.update(owner, "AWAITING_TTS")
        val expectedDeadline = clock.alarms.last().at
        clock.advance(10_000)
        listOf("LISTENING", "VOICE_STARTED", "STARTING_TTS", "NOT_A_STAGE").forEach {
            clock.controller.update(owner, it)
        }
        assertEquals(FeedbackPhase.THINKING, clock.phase())
        assertEquals(2, clock.alarms.size)
        assertEquals(expectedDeadline, clock.alarms.last().at)
    }

    @Test fun listeningAndThinkingDeadlinesClearWithoutRevivingOnLateEvents() {
        val clock = Clock()
        val owner = Any()
        clock.controller.begin(owner)
        clock.advance(VoiceFeedbackController.LISTENING_MS)
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
        clock.controller.update(owner, "STREAMING_TTS")
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
        clock.controller.begin(Any())
        val next = Any()
        clock.controller.begin(next)
        clock.controller.update(next, "VOICE_STOPPED")
        clock.advance(VoiceFeedbackController.THINKING_MS)
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
    }

    @Test fun totalTurnDeadlineCapsLongSpeakingButDoesNotTruncateOrdinarySpeech() {
        val clock = Clock()
        val owner = Any()
        clock.controller.begin(owner)
        clock.advance(40_000)
        clock.controller.update(owner, "AWAITING_RESPONSE")
        clock.advance(115_000)
        clock.controller.update(owner, "STREAMING_TTS")
        assertEquals(VoiceFeedbackController.MAX_TURN_MS, clock.alarms.last().at)
        clock.advance(60_000)
        assertEquals(FeedbackPhase.SPEAKING, clock.phase())
        clock.advance(VoiceFeedbackController.MAX_TURN_MS - clock.now)
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
    }

    @Test fun lifecycleClearInvalidatesEveryPendingCallbackAndAllowsNextTurn() {
        val clock = Clock()
        val old = Any()
        clock.controller.begin(old)
        val deadline = clock.alarms.last()
        clock.controller.clearAll()
        assertFalse(clock.controller.owns(old))
        val next = Any()
        clock.controller.begin(next)
        deadline.action()
        clock.controller.update(old, "STREAMING_TTS")
        assertEquals(FeedbackPhase.LISTENING, clock.phase())
        clock.controller.update(next, "ENDED")
        assertEquals(FeedbackPhase.HIDDEN, clock.phase())
    }
}

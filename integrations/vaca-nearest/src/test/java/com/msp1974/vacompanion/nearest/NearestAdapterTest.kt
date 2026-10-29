package com.msp1974.vacompanion.nearest

import org.junit.Assert.*
import org.junit.Test
import java.net.InetAddress

class NearestAdapterTest {
    @Test fun disabledArbitrationLeavesActivePipelineRecoveryToLocalHandler() {
        var idleChecks = 0
        assertTrue(nearestWakeAllowed(false, { idleChecks++; false }, { true }))
        // The existing local handler, not arbitration, applies its 15s/30s timeout checks.
        assertEquals(0, idleChecks)
    }
    @Test fun disabledArbitrationStillHonorsCaptureInhibitors() {
        assertFalse(nearestWakeAllowed(false, { error("Idle check must not replace the capture guard") }, { false }))
    }
    @Test fun enabledArbitrationStillRequiresAnIdlePipeline() {
        assertFalse(nearestWakeAllowed(true, { false }, { error("Use the coordinated admission guard") }))
        assertTrue(nearestWakeAllowed(true, { true }, { false }))
    }
    @Test fun bufferedProducerCannotReplayTheCurrentOrFutureFrame() {
        val b = PrerollBuffer()
        (1L..8).forEach { b.add(shortArrayOf(it.toShort()), it * 80, it * 80, it) }
        // Producer is already at frame 8 when buffered consumer receives frame 5.
        val replay = b.beforeSequence(160, 5)
        assertEquals(listOf(2L, 3L, 4L), replay.map { it.sequence })
        assertEquals(listOf(2, 3, 4), replay.map { it.pcm[0].toInt() })
    }
    @Test fun captureDuringElectionAndPipelineSetupIsPreservedOnce() {
        val b = PrerollBuffer()
        (1L..9).forEach { b.add(shortArrayOf(it.toShort()), it * 80, it * 80, it) }
        // Election ended at 400 ms, HA starts streaming at 640 ms. Include that gap.
        val joined = b.beforeSequence(160, 8).map { it.sequence } + listOf(8L, 9L)
        assertEquals((2L..9).toList(), joined)
        assertEquals(joined.size, joined.distinct().size)
    }
    @Test fun memoryAndTimeBoundsKeepRecentSamples() {
        val b = PrerollBuffer(maxBytes = 8, maxAgeMs = 100)
        b.add(shortArrayOf(1, 2), 1, 1, 1)
        b.add(shortArrayOf(3, 4), 2, 2, 2)
        b.add(shortArrayOf(5, 6), 3, 3, 3)
        assertEquals(8, b.sizeBytes())
        assertEquals(listOf(2L, 3L), b.beforeSequence(0, 99).map { it.sequence })
        b.add(shortArrayOf(7), 104, 104, 4)
        assertEquals(listOf(4L), b.beforeSequence(0, 99).map { it.sequence })
        b.clear(); assertEquals(0, b.sizeBytes()); assertTrue(b.beforeSequence(0, 99).isEmpty())
    }
    @Test fun historyOwnsSamplesAndDoesNotExposeItsArrays() {
        val b = PrerollBuffer(); val input = shortArrayOf(0x1234)
        b.add(input, 0, 0, 1); input[0] = 0
        val first = b.beforeSequence(0, 2).single(); first.pcm.fill(0)
        val second = b.beforeSequence(0, 2).single()
        assertArrayEquals(byteArrayOf(0x34, 0x12), second.pcm)
    }
    @Test fun duplicateWakeStaysBlockedUntilPipelineOpenCompletes() {
        val gate = WakeTurnGuard(); val token = gate.begin()!!
        assertNull(gate.begin())
        assertTrue(gate.current(token))
        // Simulate suspended pipeline-open callback; no finish until it returns.
        assertNull(gate.begin()); assertTrue(gate.finish(token))
        assertNotNull(gate.begin())
    }
    @Test fun stopMuteAndManualWakeInvalidatePendingCompletion() {
        val gate = WakeTurnGuard(); val old = gate.begin()!!
        gate.cancel(); val newer = gate.begin()!!
        assertFalse(gate.current(old)); assertFalse(gate.finish(old))
        assertNull(gate.begin()); assertTrue(gate.current(newer)); assertTrue(gate.finish(newer))
    }
    @Test fun targetsAreLimitedToPrivateLanAddresses() {
        fun ip(vararg bytes: Int) = InetAddress.getByAddress(bytes.map { it.toByte() }.toByteArray())
        assertTrue(NearestLan.accepts(ip(10, 1, 2, 3)))
        assertTrue(NearestLan.accepts(ip(172, 16, 1, 1)))
        assertTrue(NearestLan.accepts(ip(192, 168, 1, 1)))
        assertTrue(NearestLan.accepts(ip(169, 254, 1, 2)))
        assertFalse(NearestLan.accepts(ip(127, 0, 0, 1)))
        assertFalse(NearestLan.accepts(ip(0, 0, 0, 0)))
        assertFalse(NearestLan.accepts(ip(224, 1, 2, 3)))
        assertFalse(NearestLan.accepts(ip(8, 8, 8, 8)))
        assertFalse(NearestLan.accepts(ip(172, 15, 0, 1)))
    }
    @Test fun importedNonemptyLegacyHouseWordsRemainCompatible() {
        listOf("x", "test").forEach { legacy ->
            NearestConfig(enabled = true, name = "fixture", houseWord = legacy).validate()
        }
    }
    @Test(expected = IllegalArgumentException::class)
    fun emptyHouseWordCannotEnableCoordination() {
        NearestConfig(enabled = true, name = "fixture", houseWord = "").validate()
    }
    @Test fun blankInputPreservesLegacyAndLongReplacementIsAccepted() {
        assertEquals("test", NearestConfig.houseWordFromInput("", "test"))
        val replacement = "fictional-new-house-word"
        assertEquals(replacement, NearestConfig.houseWordFromInput(replacement, "test"))
    }
    @Test fun newlyEnteredShortHouseWordsAreRejected() {
        listOf("x", "test", "a".repeat(15)).forEach { input ->
            assertThrows(IllegalArgumentException::class.java) {
                NearestConfig.houseWordFromInput(input, "fixture-previous-word")
            }
        }
    }

    @Test fun abortedOpenCannotLeakItsHistoryToAContinuation() {
        val replay = NearestReplay()
        replay.arm(1, 100, 400)
        replay.finishOpen(1, completed = true) // Local handler returned before creating a pipeline.
        val continuation = Any()
        replay.bind(null, continuation)
        assertNull(replay.take(continuation))
    }
    @Test fun thrownOpenClearsEvenAProvisionalPipelineBinding() {
        val replay = NearestReplay(); val pipeline = Any()
        replay.arm(1, 100, 400); replay.bind(1, pipeline)
        replay.finishOpen(1, completed = false)
        assertNull(replay.take(pipeline))
    }
    @Test fun onlyTheWinningPipelineCanDrainItsReplayOnce() {
        val replay = NearestReplay(); val winner = Any()
        replay.arm(1, 100, 400); replay.bind(1, winner)
        replay.finishOpen(1, completed = true)
        assertNull(replay.take(Any()))
        assertEquals(NearestReplay.Window(100, 400), replay.take(winner))
        assertNull(replay.take(winner))
    }
    @Test fun uncoordinatedWakeOrFollowupDropsPreviousReplay() {
        val replay = NearestReplay(); val previous = Any(); val next = Any()
        replay.arm(1, 100, 400); replay.bind(1, previous)
        replay.bind(2, next) // A new local wake without an election replay window.
        assertNull(replay.take(previous)); assertNull(replay.take(next))
        replay.arm(3, 500, 800); replay.bind(3, previous)
        replay.bind(null, next) // CONTINUE_CONVERSATION, manual, or server-initiated turn.
        assertNull(replay.take(previous)); assertNull(replay.take(next))
    }
    @Test fun staleOpenCompletionCannotClearANewerTurn() {
        val replay = NearestReplay(); val current = Any()
        replay.arm(1, 100, 400)
        replay.arm(2, 500, 800); replay.bind(2, current)
        replay.finishOpen(1, completed = false)
        assertEquals(NearestReplay.Window(500, 800), replay.take(current))
    }
    @Test fun oldPipelineFinishCannotDiscardTheCurrentPipelineHistory() {
        val replay = NearestReplay(); val previous = Any(); val current = Any()
        replay.arm(2, 500, 800); replay.bind(2, current)
        replay.release(previous)
        assertEquals(NearestReplay.Window(500, 800), replay.take(current))
    }
    @Test fun pipelineFinishAndCancellationDiscardUndrainedAudio() {
        val replay = NearestReplay(); val pipeline = Any()
        replay.arm(1, 100, 400); replay.bind(1, pipeline); replay.release(pipeline)
        assertNull(replay.take(pipeline))
        replay.arm(2, 500, 800); replay.bind(2, pipeline); replay.clear()
        assertNull(replay.take(pipeline))
    }
    @Test fun stoppedAndInitializingRuntimeRejectsWakesAndClaims() {
        val lifecycle = NearestLifecycle()
        assertFalse(lifecycle.active)
        val request = lifecycle.start(); val transport = lifecycle.replaceTransport()
        assertFalse(lifecycle.active); assertFalse(lifecycle.acceptsClaim(transport))
        assertTrue(lifecycle.activate(request))
        assertTrue(lifecycle.active); assertTrue(lifecycle.acceptsClaim(transport))
        lifecycle.pause()
        assertFalse(lifecycle.active); assertFalse(lifecycle.acceptsClaim(transport))
    }
    @Test fun listenerPauseAndResumePreserveTransportGeneration() {
        val lifecycle = NearestLifecycle()
        val first = lifecycle.start(); val retainedTransport = lifecycle.replaceTransport()
        lifecycle.activate(first); lifecycle.pause()
        val resumed = lifecycle.start()
        assertFalse(lifecycle.acceptsClaim(retainedTransport))
        lifecycle.activate(resumed)
        assertTrue(lifecycle.acceptsClaim(retainedTransport))
    }
    @Test fun stopInvalidatesInflightInitializationAndQueuedReload() {
        val lifecycle = NearestLifecycle(); val pending = lifecycle.start()
        lifecycle.pause()
        assertFalse(lifecycle.activate(pending)); assertNull(lifecycle.reload(pending))
        assertFalse(lifecycle.active)
        val current = lifecycle.start()
        assertFalse(lifecycle.activate(pending)); assertNull(lifecycle.reload(pending))
        assertTrue(lifecycle.activate(current))
    }
    @Test fun changedConfigurationRejectsOldTransportCallbacks() {
        val lifecycle = NearestLifecycle(); val first = lifecycle.start()
        val previous = lifecycle.replaceTransport(); lifecycle.activate(first)
        val reloaded = lifecycle.reload(first)!!
        assertFalse(lifecycle.active)
        val replacement = lifecycle.replaceTransport(); lifecycle.activate(reloaded)
        assertFalse(lifecycle.acceptsClaim(previous)); assertTrue(lifecycle.acceptsClaim(replacement))
    }
    @Test fun identicalSettingsReuseTransportWithoutCredentialDisclosure() {
        val first = NearestConfig(true, "fixture", "fictional-house-word", 300, 1.0, 18127)
        val second = NearestConfig(true, "fixture", "fictional-house-word", 300, 1.0, 18127)
        assertTrue(first.sameConfiguration(second))
        assertFalse(first.toString().contains("fictional-house-word"))
        listOf(
            NearestConfig(false, "fixture", "fictional-house-word", 300, 1.0, 18127),
            NearestConfig(true, "renamed", "fictional-house-word", 300, 1.0, 18127),
            NearestConfig(true, "fixture", "changed-fictional-word", 300, 1.0, 18127),
            NearestConfig(true, "fixture", "fictional-house-word", 200, 1.0, 18127),
            NearestConfig(true, "fixture", "fictional-house-word", 300, 2.0, 18127),
            NearestConfig(true, "fixture", "fictional-house-word", 300, 1.0, 18128),
        ).forEach { assertFalse(first.sameConfiguration(it)) }
    }

}

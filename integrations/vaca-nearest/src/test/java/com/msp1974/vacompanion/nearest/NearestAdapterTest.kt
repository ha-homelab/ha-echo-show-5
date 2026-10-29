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

}

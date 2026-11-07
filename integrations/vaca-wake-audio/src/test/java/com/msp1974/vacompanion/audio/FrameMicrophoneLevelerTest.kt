package com.msp1974.vacompanion.audio

import org.junit.Assert.*
import org.junit.Test
import kotlin.math.abs
import kotlin.math.sin

class FrameMicrophoneLevelerTest {
    private fun signal(size: Int, amplitude: Int = 100) =
        ShortArray(size) { (sin(it * 0.13) * amplitude).toInt().toShort() }

    @Test fun fragmentedReadsPreserveEverySampleAndDecision() {
        val input = signal(320 * 300)
        val whole = FrameMicrophoneLeveler().process(input)
        val fragmented = FrameMicrophoneLeveler()
        val output = mutableListOf<Short>()
        var offset = 0
        val sizes = intArrayOf(1, 127, 512, 1280, 2048, 7)
        var index = 0
        while (offset < input.size) {
            val end = minOf(input.size, offset + sizes[index++ % sizes.size])
            output.addAll(fragmented.process(input.copyOfRange(offset, end)).toList())
            offset = end
        }
        assertArrayEquals(whole, output.toShortArray())
    }

    @Test fun quietFirstPhraseGetsImmediateGain() {
        val leveler = FrameMicrophoneLeveler()
        assertTrue(leveler.process(ShortArray(320 * 100)).all { it == 0.toShort() })
        val input = signal(320, 20)
        assertArrayEquals(input.map { (it * 10).toShort() }.toShortArray(), leveler.process(input))
    }

    @Test fun quietIntervalsDoNotEraseEstablishedGain() {
        val leveler = FrameMicrophoneLeveler()
        val first = leveler.process(signal(320, 10))
        leveler.process(ShortArray(320 * 500))
        assertArrayEquals(first, leveler.process(signal(320, 10)))
    }

    @Test fun transientPeaksNeverClipIncludingMinimumShort() {
        val input = ShortArray(320) { if (it % 2 == 0) Short.MIN_VALUE else Short.MAX_VALUE }
        val output = FrameMicrophoneLeveler().process(input)
        assertTrue(output.all { abs(it.toInt()) <= 23198 })
        assertTrue(output[0] < 0 && output[1] > 0)
    }

    @Test fun resetDiscardsPartialFrameAndLearnedAttenuation() {
        val leveler = FrameMicrophoneLeveler()
        leveler.process(ShortArray(320) { Short.MAX_VALUE })
        assertEquals(0, leveler.process(shortArrayOf(42)).size)
        leveler.reset()
        assertArrayEquals(FrameMicrophoneLeveler().process(signal(320)), leveler.process(signal(320)))
    }

    @Test fun gainSettingIsBoundedAndRepeatedCallsDoNotCompoundIt() {
        val leveler = FrameMicrophoneLeveler()
        repeat(100) { leveler.setMicGainDb(-100f) }
        val input = signal(320, 10)
        val output = leveler.process(input)
        assertTrue(output.indices.all { abs(output[it].toInt()) <= abs(input[it].toInt()) * 4 })
        assertTrue(output.any { abs(it.toInt()) > 10 })
    }

    @Test fun emptyInputDoesNotFlushOrLosePartialFrames() {
        val leveler = FrameMicrophoneLeveler()
        assertEquals(0, leveler.process(ShortArray(319)).size)
        assertEquals(0, leveler.process(shortArrayOf()).size)
        assertEquals(320, leveler.process(shortArrayOf(0)).size)
    }
}

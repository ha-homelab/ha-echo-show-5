package com.msp1974.vacompanion.audio

import kotlin.math.abs
import kotlin.math.exp
import kotlin.math.pow
import kotlin.math.sqrt

/** Speech leveling in fixed 20 ms frames. No audio is retained beyond one frame.
 *
 * Uses the published TECHO5 operating parameters, independently implemented for
 * Android PCM16: hold gain in quiet intervals, follow speech slowly, and apply
 * an immediate peak ceiling. Unlike sample-envelope AGC, gain is constant within
 * each frame and a quiet onset does not have to open a gain gate first.
 */
internal class FrameMicrophoneLeveler {
    private val pending = ShortArray(FRAME_SAMPLES)
    private var pendingSize = 0
    private var floor = FULL_SCALE
    private var gain = 10.0
    private var gainDb = 0.0

    fun setMicGainDb(value: Float) {
        val next = value.toDouble().coerceIn(-10.0, 10.0)
        if (next != gainDb) {
            gain *= db(next - gainDb)
            gainDb = next
        }
    }

    fun reset() {
        pending.fill(0)
        pendingSize = 0
        floor = FULL_SCALE
        gain = db(20.0 + gainDb)
    }

    /** Emits complete frames only; arbitrary read fragmentation never changes gain decisions. */
    fun process(input: ShortArray): ShortArray {
        val output = ShortArray((pendingSize + input.size) / FRAME_SAMPLES * FRAME_SAMPLES)
        var offset = 0
        var written = 0
        while (offset < input.size) {
            val count = minOf(FRAME_SAMPLES - pendingSize, input.size - offset)
            input.copyInto(pending, pendingSize, offset, offset + count)
            pendingSize += count
            offset += count
            if (pendingSize == FRAME_SAMPLES) {
                level(output, written)
                written += FRAME_SAMPLES
                pendingSize = 0
            }
        }
        return output
    }

    private fun level(output: ShortArray, offset: Int) {
        var power = 0.0
        var peak = 0
        for (sample in pending) {
            val value = sample.toInt()
            power += value.toDouble() * value
            peak = maxOf(peak, abs(value))
        }
        val rms = sqrt(power / FRAME_SAMPLES)
        floor = maxOf(16.0, floor + (rms - floor) * follow(if (rms < floor) 0.2 else 60.0))
        if (rms > floor * db(12.0)) {
            val wanted = (FULL_SCALE * db(-23.0 + gainDb) / rms).coerceIn(1.0, db(27.0 + gainDb))
            gain += (wanted - gain) * follow(if (wanted < gain) 0.5 else 5.0)
        }
        if (peak > 0) gain = minOf(gain, FULL_SCALE * db(-3.0) / peak)
        for (i in pending.indices) {
            output[offset + i] = (pending[i] * gain).toInt().coerceIn(-32768, 32767).toShort()
        }
    }

    companion object {
        const val FRAME_SAMPLES = 320
        private const val FULL_SCALE = 32768.0
        private fun db(value: Double) = 10.0.pow(value / 20.0)
        private fun follow(seconds: Double) = 1.0 - exp(-0.02 / seconds)
    }
}

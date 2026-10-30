package com.msp1974.vacompanion.nearest

import kotlin.math.PI
import kotlin.math.exp
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.pow
import kotlin.math.sqrt

/** TECHO5-compatible speech-over-room score for mono PCM16 at 16 kHz.
 * Feed continuously after acoustic echo cancellation, before noise suppression or gain control.
 * The device-specific quantisation floor is configurable; the Dot's default is 16 PCM units.
 * This is a hearing-quality comparison, not a physical distance measurement.
 */
class StandoutScore(floorMinimum: Float = 16f) {
    private val lp = FloatArray(3)
    private var hp = 0f
    private var floor = 0f
    private var power = 0.0
    private var frames = 0
    private val recent = FloatArray(20)
    private var at = 0
    private var count = 0
    private val frame = ShortArray(320)
    private var filled = 0
    private var minimum = checkedFloor(floorMinimum)
    private val lowPass = (1 - exp(-2 * PI * 900 / 16000)).toFloat()
    private val highPass = (1 - exp(-2 * PI * 200 / 16000)).toFloat()
    private val down = (1 - exp(-0.020 / 0.200)).toFloat()
    private val up = (1 - exp(-0.020 / 60.0)).toFloat()

    @Synchronized
    fun setFloorMinimum(value: Float) { minimum = checkedFloor(value) }

    @Synchronized
    fun add(samples: ShortArray) { add(samples, 0, samples.size) }

    @Synchronized
    fun add(samples: ShortArray, offset: Int, length: Int) {
        require(offset >= 0 && length >= 0 && offset <= samples.size - length)
        var i = offset
        val end = offset + length
        while (i < end) {
            val take = minOf(frame.size - filled, end - i)
            samples.copyInto(frame, filled, i, i + take)
            filled += take; i += take
            if (filled == frame.size) { measure(); filled = 0 }
        }
    }

    @Synchronized
    fun score(): Double {
        var best = 0f
        for (i in 1..minOf(12, count)) best = max(best, recent[(at - i + recent.size) % recent.size])
        return best.toDouble()
    }

    @Synchronized
    fun reset() {
        lp.fill(0f); hp = 0f; floor = 0f; power = 0.0; frames = 0
        recent.fill(0f); at = 0; count = 0; frame.fill(0); filled = 0
    }

    private fun measure() {
        var energy = 0.0
        for (sample in frame) {
            var x = sample.toFloat()
            for (pole in lp.indices) { lp[pole] += (x - lp[pole]) * lowPass; x = lp[pole] }
            hp += (x - hp) * highPass
            x -= hp
            energy += x.toDouble() * x.toDouble()
        }
        val meanPower = energy / frame.size
        val rms = sqrt(meanPower).toFloat()
        if (floor == 0f) floor = max(rms, minimum)
        floor = max(floor + (rms - floor) * if (rms < floor) down else up, minimum)
        power += meanPower; frames++
        if (frames != 5) return
        val mean = sqrt(power / frames)
        val value = if (floor > 0f && mean > floor) minOf(20 * log10(mean / floor), 90.0).toFloat() else 0f
        recent[at] = value; at = (at + 1) % recent.size; count = minOf(count + 1, recent.size)
        power = 0.0; frames = 0
    }

    companion object {
        fun dotFloorForAnalogGain(gainDb: Int): Float = max(16.0 * 10.0.pow((gainDb - 20) / 20.0), 2.0).toFloat()
        private fun checkedFloor(value: Float): Float { require(value.isFinite() && value > 0f); return value }
    }
}

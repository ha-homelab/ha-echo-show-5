package com.msp1974.vacompanion.nearest

import java.util.ArrayDeque

/** A bounded, memory-only PCM history. Never written to the diagnostic status file. */
class PrerollBuffer(private val maxBytes: Int = 96_000, private val maxAgeMs: Long = 3000) {
    data class Frame(val monotonicMs: Long, val wallMs: Long, val pcm: ByteArray, val sequence: Long)
    private val frames = ArrayDeque<Frame>()
    private var bytes = 0
    @Synchronized fun add(samples: ShortArray, monotonicMs: Long, wallMs: Long, sequence: Long) {
        if (samples.isEmpty() || samples.size > maxBytes / 2) return
        val data = ByteArray(samples.size * 2)
        samples.forEachIndexed { i, sample -> data[2*i] = sample.toByte(); data[2*i+1] = (sample.toInt() shr 8).toByte() }
        frames.addLast(Frame(monotonicMs, wallMs, data, sequence)); bytes += data.size
        while (frames.isNotEmpty() && (bytes > maxBytes || frames.first.monotonicMs < monotonicMs - maxAgeMs)) {
            bytes -= frames.removeFirst().pcm.size
        }
    }
    @Synchronized fun between(startMs: Long, endMs: Long): List<Frame> =
        frames.filter { it.monotonicMs >= startMs && it.monotonicMs <= endMs }.map { it.copy(pcm = it.pcm.copyOf()) }
    @Synchronized fun beforeSequence(startMs: Long, liveSequence: Long): List<Frame> =
        frames.filter { it.monotonicMs >= startMs && it.sequence < liveSequence }.map { it.copy(pcm = it.pcm.copyOf()) }
    @Synchronized fun clear() { frames.forEach { it.pcm.fill(0) }; frames.clear(); bytes = 0 }
    @Synchronized fun sizeBytes() = bytes
}

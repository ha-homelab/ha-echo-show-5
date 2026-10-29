// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

/** Decoder-independent bounds and drain accounting. Frames count only successful writes. */
internal class PcmProgress {
    var nextSequence = 0L; private set
    var writtenBytes = 0L; private set
    var pendingBytes = 0; private set
    fun begin(sequence: Long, size: Int) {
        require(sequence == nextSequence && pendingBytes == 0) { "chunk_sequence" }
        require(size in 2..16384 && size % 2 == 0 && writtenBytes + size <= MAX_BYTES) { "chunk_size" }
        pendingBytes = size
        nextSequence++
    }
    fun wrote(count: Int) {
        require(count > 0 && count <= pendingBytes && count % 2 == 0) { "write_failed" }
        writtenBytes += count
        pendingBytes -= count
    }
    fun canFinish() = pendingBytes == 0 && writtenBytes > 0
    fun drained(renderedFrames: Long) = canFinish() && renderedFrames >= writtenBytes / 2
    companion object { const val MAX_BYTES = 22050L * 2L * 120L }
}

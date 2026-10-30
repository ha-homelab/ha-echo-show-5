// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioTrack
import android.os.Handler
import android.os.Looper

/** Owns exactly one AudioTrack. It never changes system volume or stops another player. */
internal class AnnouncementAudio(context: Context, private val sharedMusicFocus: Boolean = false, onFocusLost: () -> Unit) {
    private val manager = context.getSystemService(AudioManager::class.java)
    private val attributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ASSISTANT)
        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build()
    private val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_EXCLUSIVE)
        .setAudioAttributes(attributes).setAcceptsDelayedFocusGain(false)
        .setOnAudioFocusChangeListener({ change -> if (change != AudioManager.AUDIOFOCUS_GAIN) onFocusLost() }, Handler(Looper.getMainLooper())).build()
    private var track: AudioTrack? = null
    @Volatile var closed = false; private set
    private var closeFailed = false
    fun start() {
        check(sharedMusicFocus || manager.requestAudioFocus(focus) == AudioManager.AUDIOFOCUS_REQUEST_GRANTED) { "focus_denied" }
        try {
            val minimum = AudioTrack.getMinBufferSize(22050, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
            check(minimum > 0)
            track = AudioTrack.Builder().setAudioAttributes(attributes)
                .setAudioFormat(AudioFormat.Builder().setSampleRate(22050).setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(maxOf(minimum, 8192)).build()
            check(track!!.state == AudioTrack.STATE_INITIALIZED)
            track!!.play()
            check(track!!.playState == AudioTrack.PLAYSTATE_PLAYING)
        } catch (error: Exception) { close(); throw error }
    }
    fun write(bytes: ByteArray, offset: Int): Int {
        check(!closed)
        return checkNotNull(track).write(bytes, offset, bytes.size - offset, AudioTrack.WRITE_NON_BLOCKING)
    }
    fun renderedFrames(): Long {
        check(!closed)
        val value = checkNotNull(track)
        check(value.playState == AudioTrack.PLAYSTATE_PLAYING)
        return value.playbackHeadPosition.toLong() and 0xffffffffL
    }
    fun close() {
        if (closed) { check(!closeFailed) { "release_unconfirmed" }; return }
        closed = true
        val value = track
        track = null
        try {
            try { value?.pause(); value?.flush() } finally {
                try { value?.release() } finally { if (!sharedMusicFocus) manager.abandonAudioFocusRequest(focus) }
            }
        } catch (error: Exception) {
            closeFailed = true
            throw error
        }
    }
}

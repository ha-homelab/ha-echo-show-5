package com.msp1974.vacompanion.nearest

/** Election audio belongs to one actual pipeline, never to the next caller that happens to stream. */
internal class NearestReplay {
    data class Window(val from: Long, val unattenuatedUntil: Long)
    private data class Pending(val turn: Long, val window: Window, var pipeline: Any? = null)
    private var pending: Pending? = null

    fun arm(turn: Long, from: Long, until: Long) { pending = Pending(turn, Window(from, until)) }
    fun bind(turn: Long?, pipeline: Any) {
        val current = pending
        if (turn == null || current?.turn != turn) clear()
        else current.pipeline = pipeline
    }
    fun finishOpen(turn: Long, completed: Boolean) {
        val current = pending ?: return
        if (current.turn == turn && (!completed || current.pipeline == null)) clear()
    }
    fun take(pipeline: Any): Window? {
        val current = pending ?: return null
        if (current.pipeline !== pipeline) return null
        clear()
        return current.window
    }
    fun release(pipeline: Any) { if (pending?.pipeline === pipeline) clear() }
    fun clear() { pending = null }
}

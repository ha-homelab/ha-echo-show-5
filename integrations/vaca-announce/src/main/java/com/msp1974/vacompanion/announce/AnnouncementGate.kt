// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

/** Shared admission boundary for local announcement, Assist, media and SIP creation. */
object AnnouncementGate {
    val monitor = Any()
    @Volatile private var owner: String? = null
    val busy: Boolean get() = owner != null
    fun owns(id: String): Boolean = owner == id
    fun claim(id: String, check: () -> String?): String? = synchronized(monitor) {
        if (owner != null) return@synchronized "busy"
        check()?.let { return@synchronized it }
        owner = id
        null
    }
    fun release(id: String): Boolean = synchronized(monitor) {
        if (owner != id) false else { owner = null; true }
    }
}

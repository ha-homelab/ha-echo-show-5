// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import android.app.AppOpsManager
import android.app.NotificationManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.AudioManager
import android.os.Process

/** External apps cannot join our mutex: observe conservatively, abort on change/focus loss. */
internal class AnnouncementEnvironment(private val context: Context) {
    private val audio = context.getSystemService(AudioManager::class.java)
    private val usage = context.getSystemService(UsageStatsManager::class.java)
    private var lastQuery = 0L
    private var foreground: String? = null
    fun compatibleSip(): Boolean = try {
        val pm = context.packageManager
        val info = pm.getApplicationInfo(SIP, PackageManager.GET_META_DATA)
        pm.checkSignatures(context.packageName, SIP) == PackageManager.SIGNATURE_MATCH &&
            info.metaData?.getInt("org.hahomelab.show5sip.ANNOUNCEMENT_GUARD", 0) == 1
    } catch (_: Exception) { false }
    fun usageAccess(): Boolean = try {
        context.getSystemService(AppOpsManager::class.java).checkOpNoThrow(
            AppOpsManager.OPSTR_GET_USAGE_STATS, Process.myUid(), context.packageName) == AppOpsManager.MODE_ALLOWED
    } catch (_: Exception) { false }
    fun reason(ownPlayback: Boolean = false): String? = try {
        when {
            !compatibleSip() -> "sip_guard_unavailable"
            !usageAccess() -> "usage_access_required"
            context.getSystemService(NotificationManager::class.java).currentInterruptionFilter != NotificationManager.INTERRUPTION_FILTER_ALL -> "do_not_disturb"
            audio.mode != AudioManager.MODE_NORMAL -> "communication_busy"
            !ownPlayback && audio.isMusicActive -> "media_busy"
            !foregroundAllowed() -> "external_app_busy"
            else -> null
        }
    } catch (_: Exception) { "external_state_unknown" }
    @Synchronized private fun foregroundAllowed(): Boolean {
        val now = System.currentTimeMillis()
        // Initial query is deliberately broad: a stationary room screen may be open all day.
        val from = if (lastQuery == 0L || now < lastQuery) now - 86400000 else (lastQuery - 1000).coerceAtLeast(0)
        val events = usage.queryEvents(from, now)
        val event = UsageEvents.Event()
        var seen = 0
        var latest = 0L
        while (events.hasNextEvent()) {
            if (++seen > 50000) return false
            events.getNextEvent(event)
            if (event.eventType == UsageEvents.Event.MOVE_TO_FOREGROUND && event.timeStamp >= latest) {
                foreground = event.packageName
                latest = event.timeStamp
            }
        }
        lastQuery = now
        val pkg = foreground ?: return false
        val home = context.packageManager.resolveActivity(
            Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME), PackageManager.MATCH_DEFAULT_ONLY)?.activityInfo?.packageName
        return pkg == context.packageName || (home != null && pkg == home)
    }
    companion object { const val SIP = "org.hahomelab.show5sip" }
}

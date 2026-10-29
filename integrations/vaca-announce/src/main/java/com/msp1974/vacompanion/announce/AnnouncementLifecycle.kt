// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import android.app.Activity
import android.app.Application
import android.content.Context
import android.os.Bundle
import android.view.ViewTreeObserver
import java.util.WeakHashMap

/** Only a resumed and window-focused MainActivity proves the kiosk is in front. */
internal object AnnouncementLifecycle : Application.ActivityLifecycleCallbacks {
    private data class State(var resumed: Boolean = false, var focused: Boolean = false)
    private val activities = WeakHashMap<Activity, State>()
    private val listeners = WeakHashMap<Activity, ViewTreeObserver.OnWindowFocusChangeListener>()
    private var registered = false
    private var ownActivity = ""
    @Volatile private var evidence = ForegroundState.ActivityEvidence(false, 0)

    @Synchronized fun initialize(context: Context) {
        if (registered) return
        val application = context.applicationContext as? Application ?: return
        ownActivity = application.packageName + ".MainActivity"
        application.registerActivityLifecycleCallbacks(this)
        registered = true
    }
    fun snapshot(): ForegroundState.ActivityEvidence = evidence
    private fun refresh() {
        evidence = ForegroundState.ActivityEvidence(
            activities.any { (activity, state) -> activity.javaClass.name == ownActivity && state.resumed && state.focused },
            System.currentTimeMillis(),
        )
    }
    private fun attach(activity: Activity) {
        activities.getOrPut(activity) { State() }
        if (listeners.containsKey(activity)) return
        val listener = ViewTreeObserver.OnWindowFocusChangeListener { focused ->
            activities[activity]?.let { it.focused = focused; refresh() }
        }
        activity.window.decorView.viewTreeObserver.addOnWindowFocusChangeListener(listener)
        listeners[activity] = listener
    }
    override fun onActivityCreated(activity: Activity, savedInstanceState: Bundle?) { attach(activity) }
    override fun onActivityResumed(activity: Activity) {
        attach(activity)
        activities[activity]?.let { it.resumed = true; it.focused = activity.window.decorView.hasWindowFocus() }
        refresh()
    }
    override fun onActivityPaused(activity: Activity) {
        activities[activity]?.let { it.resumed = false; it.focused = false }
        refresh()
    }
    override fun onActivityDestroyed(activity: Activity) {
        listeners.remove(activity)?.let { listener ->
            val observer = activity.window.decorView.viewTreeObserver
            if (observer.isAlive) observer.removeOnWindowFocusChangeListener(listener)
        }
        activities.remove(activity)
        refresh()
    }
    override fun onActivityStarted(activity: Activity) {}
    override fun onActivityStopped(activity: Activity) {}
    override fun onActivitySaveInstanceState(activity: Activity, outState: Bundle) {}
}

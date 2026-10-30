// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import kotlinx.coroutines.Job
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext

internal data class AnnouncementTeardown(val status: String, val reason: String, val quarantined: Boolean = false)

/** Keep the admission/duck owner until both owned resources are confirmed released. */
internal suspend fun teardownAnnouncement(
    status: String,
    reason: String,
    closeAudio: () -> Unit,
    releaseMusic: suspend () -> Unit,
): AnnouncementTeardown = withContext(NonCancellable) {
    try { closeAudio() }
    catch (_: Exception) { return@withContext AnnouncementTeardown("unknown", "release_failed", true) }
    try { releaseMusic() }
    catch (_: Exception) { return@withContext AnnouncementTeardown("unknown", "duck_release_failed", true) }
    AnnouncementTeardown(status, reason)
}

/** Watchdog expiry must finish its own journal update without cancelling itself. */
internal suspend fun finishAnnouncementGuarded(watchdog: Job?, cleanup: suspend () -> Unit) {
    val current = currentCoroutineContext()[Job]
    watchdog?.takeIf { it !== current }?.cancel()
    withContext(NonCancellable) { cleanup() }
}

// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** The hint interrupts an ongoing write; the locked reread also catches a claim in progress. */
internal suspend fun preemptAnnouncementOwner(
    mutex: Mutex,
    owner: () -> String?,
    signal: (String) -> Unit,
    finish: suspend (String) -> Unit,
) {
    owner()?.let(signal)
    mutex.withLock {
        owner()?.let { current -> signal(current); finish(current) }
    }
}

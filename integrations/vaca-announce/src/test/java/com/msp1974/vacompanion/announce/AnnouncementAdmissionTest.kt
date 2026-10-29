// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import org.junit.Assert.*
import org.junit.Test

class AnnouncementAdmissionTest {
    private val app = "example.kiosk"
    private val home = "example.home"
    private fun focus(at: Long) = ForegroundState.ActivityEvidence(true, at)
    private fun background(at: Long = 0) = ForegroundState.ActivityEvidence(false, at)

    @Test fun oldFocusedKioskDoesNotNeedARecentUsageEvent() {
        val state = ForegroundState()
        state.complete(3 * ForegroundState.LOOKBACK_MS)
        assertTrue(state.allows(app, home, focus(1)))
    }
    @Test fun noActivityEvidenceCannotBecomeForeground() {
        assertFalse(ForegroundState().allows(app, home, background()))
    }
    @Test fun newerExternalActivityDefeatsStaleOwnFocus() {
        val state = ForegroundState(); state.resumed("external.call", 200)
        assertFalse(state.allows(app, home, focus(100)))
    }
    @Test fun explicitNewOwnFocusSupersedesOldExternalEvent() {
        val state = ForegroundState(); state.resumed("external.call", 100)
        assertTrue(state.allows(app, home, focus(200)))
    }
    @Test fun ownUsageEventCannotOverrideActualFocusLoss() {
        val state = ForegroundState(); state.resumed(app, 100)
        assertFalse(state.allows(app, home, background(200)))
    }
    @Test fun ownPauseClearsUsageFallback() {
        val state = ForegroundState(); state.resumed(app, 100); state.paused(app, 200)
        assertFalse(state.allows(app, home, background(200)))
    }
    @Test fun recentLauncherRemainsAllowed() {
        val state = ForegroundState(); state.resumed(home, 300)
        assertTrue(state.allows(app, home, background(200)))
    }
    @Test fun staleLauncherCannotOverrideMoreRecentOwnLifecycle() {
        val state = ForegroundState(); state.resumed(home, 100)
        assertFalse(state.allows(app, home, background(200)))
    }
    @Test fun overflowDiscardsPartialStateAndAdvancesCursor() {
        val now = 3 * ForegroundState.LOOKBACK_MS
        val state = ForegroundState(); state.resumed(home, now - 10); state.failed(now)
        assertFalse(state.allows(app, home, background()))
        assertEquals(now - ForegroundState.OVERLAP_MS, state.queryStart(now + 100))
    }
    @Test fun ownLifecycleAllowsRecoveryOnNextCompleteScanAfterOverflow() {
        val state = ForegroundState(); state.failed(10000); state.complete(10100)
        assertTrue(state.allows(app, home, focus(9000)))
    }
    @Test fun newExternalEvidenceAfterOverflowStillRejects() {
        val state = ForegroundState(); state.failed(10000); state.resumed("external.call", 10010); state.complete(10100)
        assertFalse(state.allows(app, home, focus(9000)))
    }
    @Test fun olderOverlappingEventsCannotReplaceNewerActivity() {
        val state = ForegroundState(); state.resumed("external.call", 300); state.resumed(home, 100)
        assertFalse(state.allows(app, home, background()))
    }
    @Test fun stalePauseDoesNotClearNewerResume() {
        val state = ForegroundState(); state.resumed(home, 300); state.paused(home, 100)
        assertTrue(state.allows(app, home, background()))
    }
    @Test fun clockRollbackInvalidatesCachedLauncher() {
        val state = ForegroundState(); state.resumed(home, 200); state.complete(200)
        state.queryStart(100)
        assertFalse(state.allows(app, home, background()))
    }
    @Test fun preemptionSeesOwnerAssignedAfterClaimGate() = runBlocking {
        val mutex = Mutex(locked = true)
        var owner: String? = null
        val finished = mutableListOf<String>()
        val work = launch(start = CoroutineStart.UNDISPATCHED) {
            preemptAnnouncementOwner(mutex, { owner }, {}, { finished.add(it) })
        }
        assertFalse(work.isCompleted)
        owner = "claim-being-persisted"
        mutex.unlock(); work.join()
        assertEquals(listOf("claim-being-persisted"), finished)
    }
    @Test fun preemptionRereadsOwnerAfterWaiting() = runBlocking {
        val mutex = Mutex(locked = true)
        var owner: String? = "old"
        val hinted = mutableListOf<String>(); val finished = mutableListOf<String>()
        val work = launch(start = CoroutineStart.UNDISPATCHED) {
            preemptAnnouncementOwner(mutex, { owner }, { hinted.add(it) }, { finished.add(it) })
        }
        assertEquals(listOf("old"), hinted)
        owner = "current"
        mutex.unlock(); work.join()
        assertEquals(listOf("old", "current"), hinted)
        assertEquals(listOf("current"), finished)
    }
    @Test fun vanishedOwnerIsNotStoppedByOldHint() = runBlocking {
        val mutex = Mutex(locked = true)
        var owner: String? = "old"
        val finished = mutableListOf<String>()
        val work = launch(start = CoroutineStart.UNDISPATCHED) {
            preemptAnnouncementOwner(mutex, { owner }, {}, { finished.add(it) })
        }
        owner = null; mutex.unlock(); work.join()
        assertTrue(finished.isEmpty())
    }
    @Test fun idlePreemptionIsNoOp() = runBlocking {
        preemptAnnouncementOwner(Mutex(), { null }, { fail("unexpected hint") }, { fail("unexpected stop") })
    }
}

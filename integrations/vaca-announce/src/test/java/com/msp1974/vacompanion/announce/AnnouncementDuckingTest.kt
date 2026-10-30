// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import kotlinx.coroutines.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Test

class AnnouncementDuckingTest {
    private val a = "announce-" + "a".repeat(32) + "-225"
    private val b = "announce-" + "b".repeat(32) + "-226"
    private val hash = "1".repeat(64)
    @After fun cleanup() { AnnouncementGate.release(a); AnnouncementGate.release(b) }
    private fun volume(expected: Float, gain: OwnedMusicGain) = assertEquals(expected, gain.output, 0.00001f)
    private fun ledger(rows: List<AnnouncementLedger.Record> = emptyList()) =
        AnnouncementLedger(rows, { 1000 }, { 10 }, { _, _ -> }, { "music_busy" })
    @Test fun ordinaryVolumeUnchanged() { val g = OwnedMusicGain(); g.setTarget(.8f); volume(.8f, g) }
    @Test fun ownedDuckIsMultiplicative() { val g = OwnedMusicGain(); g.setTarget(.8f); assertTrue(g.begin(a)); volume(.16f, g) }
    @Test fun userVolumeChangesSurviveRelease() { val g = OwnedMusicGain(); g.begin(a); g.setTarget(.4f); volume(.08f, g); g.end(a); volume(.4f, g) }
    @Test fun userMuteSurvivesRelease() { val g = OwnedMusicGain(); g.begin(a); g.setTarget(0f); g.end(a); volume(0f, g) }
    @Test fun queueTrackGetsCurrentDuckNotOldSnapshot() { val g = OwnedMusicGain(); g.setTarget(.7f); g.begin(a); g.setTarget(.9f); volume(.18f, g); g.end(a); volume(.9f, g) }
    @Test fun repeatedClaimDoesNotDoubleDuck() { val g = OwnedMusicGain(); assertTrue(g.begin(a)); assertFalse(g.begin(a)); volume(.2f, g) }
    @Test fun secondOwnerCannotReplaceDuck() { val g = OwnedMusicGain(); g.begin(a); assertFalse(g.begin(b)); assertEquals(a, g.owner) }
    @Test fun foreignStopCannotRemoveDuck() { val g = OwnedMusicGain(); g.begin(a); assertFalse(g.end(b)); volume(.2f, g) }
    @Test fun staleStopCannotChangeNextOwner() { val g = OwnedMusicGain(); g.begin(a); g.end(a); g.begin(b); assertFalse(g.end(a)); volume(.2f, g) }
    @Test fun focusGainCannotRemoveAnnouncementFactor() { val g = OwnedMusicGain(); g.begin(a); g.focusLost(.3f); g.focusGained(); volume(.2f, g) }
    @Test fun announcementEndCannotUndoExternalFocusDuck() { val g = OwnedMusicGain(); g.begin(a); g.focusLost(.3f); g.end(a); volume(.3f, g) }
    @Test fun userTargetRetainedAcrossBothDucks() { val g = OwnedMusicGain(); g.begin(a); g.focusLost(.3f); g.setTarget(.7f); g.end(a); volume(.3f, g); g.focusGained(); volume(.7f, g) }
    @Test fun allTerminalStatesRemoveOnlyOwnedFactor() {
        for (status in AnnouncementLedger.TERMINAL) {
            val g = OwnedMusicGain(); g.begin(a); g.setTarget(.6f)
            val l = AnnouncementLedger(emptyList(), { 1000 }, { 10 }, { _, _ -> }, { null })
            assertTrue(l.claim(a, hash, 2000, "duck_music").fresh)
            assertTrue(g.end(a)); l.finish(a, status)
            volume(.6f, g); assertFalse(AnnouncementGate.busy)
        }
    }
    @Test fun newPlayerHasNoInheritedOwnerOrSnapshot() { val old = OwnedMusicGain(); old.begin(a); val replacement = OwnedMusicGain(); replacement.setTarget(.5f); assertFalse(replacement.end(a)); volume(.5f, replacement) }
    @Test(expected = IllegalArgumentException::class) fun nonFiniteVolumeRejected() { OwnedMusicGain().setTarget(Float.NaN) }
    @Test fun defaultSkipStillRejectsMusic() { assertEquals("music_busy", ledger().claim(a, hash, 2000).reason) }
    @Test fun explicitSkipStillDeduplicatesOldRecord() { val row = AnnouncementLedger.Record(a, hash, 2000, "completed"); assertEquals("completed", ledger(listOf(row)).claim(a, hash, 2000, "skip").status) }
    @Test fun duckCannotReuseOldSkipRequest() { val row = AnnouncementLedger.Record(a, hash, 2000, "completed"); assertEquals("request_conflict", ledger(listOf(row)).claim(a, hash, 2000, "duck_music").reason) }
    @Test fun skipCannotReuseDuckRequest() { val row = AnnouncementLedger.Record(a, hash, 2000, "completed", busyPolicy = "duck_music"); assertEquals("request_conflict", ledger(listOf(row)).claim(a, hash, 2000).reason) }
    @Test fun restartRetainsDuckPolicy() { val row = AnnouncementLedger.Record(a, hash, 2000, "accepted", busyPolicy = "duck_music"); val l = ledger(listOf(row)); assertEquals("duck_music", l.policy(a)); assertEquals("unknown", l.claim(a, hash, 2000, "duck_music").status) }
    @Test fun unknownPolicyCannotReserve() { assertEquals("invalid_policy", ledger().claim(a, hash, 2000, "other").reason); assertFalse(AnnouncementGate.busy) }
    @Test fun scopedDuckUsesExplicitAdmission() { assertTrue(ledger().claim(a, hash, 2000, "duck_music") { null }.fresh) }
    @Test fun firstClaimOwnsGateBeforeSecondDuck() { val l = ledger(); assertTrue(l.claim(a, hash, 2000, "duck_music") { null }.fresh); assertEquals("busy", l.claim(b, hash, 2000, "duck_music") { null }.reason) }
    @Test fun oneKnownMusicPlayerAdmitted() { assertTrue(ownedPlaybackObserved(listOf("music"), false, true)) }
    @Test fun missingExpectedMusicFailsBeforeStart() { assertFalse(ownedPlaybackObserved(emptyList(), false, true)) }
    @Test fun unknownPlaybackAlwaysRejected() { assertFalse(ownedPlaybackObserved(listOf("unknown"), false, false)); assertFalse(ownedPlaybackObserved(listOf("music", "announcement", "unknown"), true, true)) }
    @Test fun secondMusicPlayerRejected() { assertFalse(ownedPlaybackObserved(listOf("music", "music"), false, true)); assertFalse(ownedPlaybackObserved(listOf("music", "music", "announcement"), true, true)) }
    @Test fun secondAnnouncementRejected() { assertFalse(ownedPlaybackObserved(listOf("announcement", "announcement"), true, false)) }
    @Test fun ownedMusicAndAnnouncementCanCoexist() { assertTrue(ownedPlaybackObserved(listOf("music", "announcement"), true, true)) }
    @Test fun unrelatedMusicCannotEnterIdleAnnouncement() { assertFalse(ownedPlaybackObserved(listOf("music", "announcement"), true, false)) }
    @Test fun bufferedOwnedTrackCanTemporarilyHaveNoActiveConfig() { assertTrue(ownedPlaybackObserved(listOf("announcement"), true, true)) }
    @Test fun everyTerminalTeardownReleasesAudioBeforeMusic() = runBlocking {
        for (status in AnnouncementLedger.TERMINAL) {
            val calls = mutableListOf<String>()
            val result = teardownAnnouncement(status, "reason", { calls.add("audio") }, { calls.add("music") })
            assertEquals(listOf("audio", "music"), calls)
            assertEquals(status, result.status); assertFalse(result.quarantined)
        }
    }
    @Test fun uncertainAudioReleaseKeepsDuckAndQuarantines() = runBlocking {
        var released = false
        val result = teardownAnnouncement("completed", "drained", { error("failed") }, { released = true })
        assertFalse(released); assertTrue(result.quarantined); assertEquals("release_failed", result.reason)
    }
    @Test fun uncertainGainReleaseQuarantinesInsteadOfSuccess() = runBlocking {
        val result = teardownAnnouncement("completed", "drained", {}, { error("failed") })
        assertTrue(result.quarantined); assertEquals("unknown", result.status); assertEquals("duck_release_failed", result.reason)
    }
    @Test fun cancellationCannotSkipOwnedGainAndJournalRelease() = runBlocking {
        var released = false
        var journalFinished = false
        val started = CompletableDeferred<Unit>()
        val task = launch {
            try { started.complete(Unit); awaitCancellation() }
            finally { finishAnnouncementGuarded(null) {
                teardownAnnouncement("stopped", "cancelled", {}, { yield(); released = true })
                yield(); journalFinished = true
            } }
        }
        started.await(); task.cancelAndJoin(); assertTrue(released); assertTrue(journalFinished)
    }
    @Test fun watchdogExpiryDoesNotCancelItsOwnCleanupOrReturn() = runBlocking {
        var journalFinished = false
        var returned = false
        launch {
            finishAnnouncementGuarded(currentCoroutineContext()[Job]) {
                teardownAnnouncement("stopped", "expired", {}, { yield() })
                yield(); journalFinished = true
            }
            yield(); returned = true
        }.join()
        assertTrue(journalFinished); assertTrue(returned)
    }
    @Test fun normalFinishCancelsOtherWatchdog() = runBlocking {
        val watchdog = launch { awaitCancellation() }
        finishAnnouncementGuarded(watchdog) { yield() }
        watchdog.join(); assertTrue(watchdog.isCancelled)
    }

}

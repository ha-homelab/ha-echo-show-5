// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.announce

import com.msp1974.vacompanion.telephony.AudioLeaseCoordinator
import com.msp1974.vacompanion.nearest.nearestWakeAllowed
import kotlinx.coroutines.runBlocking
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

class AnnouncementCoreTest {
    private val a = "announce-" + "a".repeat(32) + "-225"
    private val b = "announce-" + "b".repeat(32) + "-226"
    private val hash = "1".repeat(64)
    private var wall = 1_000_000L
    private var elapsed = 50L
    private var stored = emptyList<AnnouncementLedger.Record>()
    private fun book(busy: () -> String? = { null }, save: (List<AnnouncementLedger.Record>) -> Unit = { stored = it }, capacity: Int = 2048) =
        AnnouncementLedger(emptyList(), { wall }, { elapsed }, save, busy, capacity)
    @After fun cleanup() { AnnouncementGate.release(a); AnnouncementGate.release(b) }
    @Test fun idleAcceptedAndDurableBeforeReturn() { assertTrue(book().claim(a, hash, wall + 1000).fresh); assertEquals("accepted", stored.single().status) }
    @Test fun invalidRequestIdRejected() { assertEquals("invalid_request", book().claim("bad", hash, wall + 1000).reason) }
    @Test fun invalidFingerprintRejected() { assertEquals("invalid_request", book().claim(a, "bad", wall + 1000).reason) }
    @Test fun expiredNeverOwns() { assertEquals("expired", book().claim(a, hash, wall).reason); assertFalse(AnnouncementGate.busy) }
    @Test fun futureExpiryBounded() { assertEquals("invalid_expiry", book().claim(a, hash, wall + 300001).reason) }
    @Test fun ciscoThreeMinuteDeadlineAccepted() { assertTrue(book().claim(a, hash, wall + 180000).fresh) }
    @Test fun busyNeverOwns() { assertEquals("sip_busy", book({ "sip_busy" }).claim(a, hash, wall + 1000).reason); assertFalse(AnnouncementGate.busy) }
    @Test fun duplicateAcceptedNeverReplays() { val l = book(); l.claim(a, hash, wall + 1000); assertFalse(l.claim(a, hash, wall + 1000).fresh) }
    @Test fun completedDuplicateNeverReplays() { val l = book(); l.claim(a, hash, wall + 1000); l.finish(a, "completed"); assertEquals("completed", l.claim(a, hash, wall + 1000).status) }
    @Test fun skippedDuplicateNeverReplays() { val l = book({ "busy" }); l.claim(a, hash, wall + 1000); assertFalse(l.claim(a, hash, wall + 1000).fresh) }
    @Test fun conflictingPayloadCannotReplay() { val l = book(); l.claim(a, hash, wall + 1000); assertEquals("request_conflict", l.claim(a, "2".repeat(64), wall + 1000).reason) }
    @Test fun conflictingExpiryCannotExtend() { val l = book(); l.claim(a, hash, wall + 1000); assertEquals("request_conflict", l.claim(a, hash, wall + 2000).reason) }
    @Test fun wrongOwnerCannotStop() { val l = book(); l.claim(a, hash, wall + 1000); l.finish(b, "stopped"); assertTrue(AnnouncementGate.owns(a)) }
    @Test fun oldStopCannotReleaseNewOwner() { val l = book(); l.claim(a, hash, wall + 1000); l.finish(a, "completed"); l.claim(b, hash, wall + 1000); l.finish(a, "stopped"); assertTrue(AnnouncementGate.owns(b)) }
    @Test fun monotonicDeadlineSurvivesWallClockBackwards() { val l = book(); l.claim(a, hash, wall + 1000); wall -= 500000; elapsed += 1001; assertTrue(l.deadlineExpired(a)) }
    @Test fun forwardWallClockExpiresEarly() { val l = book(); l.claim(a, hash, wall + 1000); wall += 2000; assertTrue(l.deadlineExpired(a)) }
    @Test fun fullLedgerNeverEvicts() { val l = book(capacity = 1); l.claim(a, hash, wall + 1000); l.finish(a, "completed"); assertEquals("ledger_full", l.claim(b, hash, wall + 1000).reason) }
    @Test fun restartConvertsInflightToUnknown() { book().claim(a, hash, wall + 1000); AnnouncementGate.release(a); val l = AnnouncementLedger(stored, { wall }, { elapsed }, { stored = it }, { null }); assertEquals("unknown", l.status(a).status); assertFalse(l.claim(a, hash, wall + 1000).fresh) }
    @Test fun failedClaimPersistenceReleasesReservation() { val l = book(save = { throw IllegalStateException() }); assertEquals("failed", l.claim(a, hash, wall + 1000).status); assertFalse(AnnouncementGate.busy) }
    @Test fun failedPlayingPersistenceStillAllowsOwnedCleanup() { var fail = false; val l = book(save = { if (fail) throw IllegalStateException() else stored = it }); l.claim(a, hash, wall + 1000); fail = true; assertEquals("unknown", l.playing(a).status); l.finish(a, "unknown"); assertFalse(AnnouncementGate.busy) }
    @Test fun uncertainTrackReleaseQuarantinesOwnership() { val l = book(); l.claim(a, hash, wall + 1000); l.finish(a, "unknown", "release_failed", releaseOwnership = false); assertTrue(AnnouncementGate.owns(a)); assertEquals("busy", l.claim(b, hash, wall + 1000).reason) }
    @Test fun simultaneousAnnouncementsOneWinner() {
        val start = CountDownLatch(1); val done = CountDownLatch(2); val pool = Executors.newFixedThreadPool(2)
        val l = book(); val wins = java.util.concurrent.atomic.AtomicInteger()
        for (id in listOf(a,b)) pool.execute { start.await(); if (l.claim(id, hash, wall + 1000).fresh) wins.incrementAndGet(); done.countDown() }
        start.countDown(); assertTrue(done.await(2, TimeUnit.SECONDS)); pool.shutdownNow(); assertEquals(1, wins.get())
    }
    @Test fun assistCreationAndClaimShareBoundary() {
        var assist = false; val l = book({ if (assist) "assist_busy" else null })
        synchronized(AnnouncementGate.monitor) { assertFalse(AnnouncementGate.busy); assist = true }
        assertEquals("assist_busy", l.claim(a, hash, wall + 1000).reason)
    }
    @Test fun sipPreemptsExactAnnouncementBeforeAcquire() = runBlocking {
        val l = book(); l.claim(a, hash, wall + 1000)
        val sip = AudioLeaseCoordinator(null, { elapsed }, {}, { !AnnouncementGate.busy }, { false }, {}, {},
            beforeAcquire = { l.finish(a, "stopped", "sip_preempted") })
        assertTrue(sip.acquire(4, "x".repeat(16), 30000, 1).ok)
        assertEquals("stopped", l.status(a).status); assertTrue(sip.inhibited)
        l.finish(a, "stopped"); assertTrue(sip.inhibited)
    }
    @Test fun incomingDuringPlayingStopsOnlyAnnouncement() = runBlocking {
        val l = book(); l.claim(a, hash, wall + 1000); l.playing(a)
        val sip = AudioLeaseCoordinator(null, { elapsed }, {}, { !AnnouncementGate.busy }, { false }, {}, {},
            beforeAcquire = { l.finish(a, "stopped", "sip_preempted") })
        assertTrue(sip.acquire(4, "x".repeat(16), 30000, 1).ok)
        assertEquals("sip_preempted", l.status(a).reason)
        l.finish(a, "stopped", "late_cancel"); assertEquals("held", sip.status(4).state)
    }
    @Test fun incomingDuringDrainCannotBeBlockedByStaleCancel() = runBlocking {
        val l = book(); l.claim(a, hash, wall + 1000); l.playing(a)
        val pcm = PcmProgress(); pcm.begin(0, 8); pcm.wrote(8); assertFalse(pcm.drained(2))
        val sip = AudioLeaseCoordinator(null, { elapsed }, {}, { !AnnouncementGate.busy }, { false }, {}, {},
            beforeAcquire = { l.finish(a, "stopped", "sip_preempted") })
        assertTrue(sip.acquire(4, "x".repeat(16), 30000, 1).ok)
        assertEquals("stopped", l.status(a).status); l.finish(a, "completed"); assertTrue(sip.inhibited)
    }
    @Test fun sipAcquiringInhibitsNewAnnouncementBeforeAsyncPreparation() = runBlocking {
        lateinit var sip: AudioLeaseCoordinator
        val l = book({ if (sip.inhibited || sip.status(-1).state != "idle") "sip_busy" else null })
        var refused = false
        sip = AudioLeaseCoordinator(null, { elapsed }, {}, { true }, { false }, {}, {},
            beforeAcquire = { refused = l.claim(a, hash, wall + 1000).reason == "sip_busy" })
        assertTrue(sip.acquire(4, "x".repeat(16), 30000, 1).ok); assertTrue(refused)
    }
    @Test fun sipReleaseRecoveryStaysUnavailable() = runBlocking {
        lateinit var sip: AudioLeaseCoordinator
        var result = ""
        val l = book({ if (sip.inhibited || sip.status(-1).state != "idle") "sip_busy" else null })
        sip = AudioLeaseCoordinator(null, { elapsed }, {}, { true }, { false }, {}, { result = l.claim(a, hash, wall + 1000).reason })
        sip.acquire(4, "x".repeat(16), 30000, 1); sip.release(4, "x".repeat(16)); assertEquals("sip_busy", result)
    }
    @Test fun disabledNearestAllowsLocalActivePipelineHandling() { assertTrue(nearestWakeAllowed(false, { false }, { true })) }
    @Test fun enabledNearestStillRequiresIdlePipeline() { assertFalse(nearestWakeAllowed(true, { false }, { true })) }
    @Test fun disabledNearestDoesNotBypassCaptureInhibitor() { assertFalse(nearestWakeAllowed(false, { true }, { false })) }
    @Test fun emptyPcmCannotComplete() { assertFalse(PcmProgress().drained(100)) }
    @Test fun partialWriteCannotComplete() { val p = PcmProgress(); p.begin(0, 8); p.wrote(4); assertFalse(p.drained(100)) }
    @Test fun drainedRequiresEveryFrame() { val p = PcmProgress(); p.begin(0,8); p.wrote(4); p.wrote(4); assertFalse(p.drained(3)); assertTrue(p.drained(4)) }
    @Test(expected = IllegalArgumentException::class) fun zeroWriteRejected() { val p = PcmProgress(); p.begin(0,8); p.wrote(0) }
    @Test(expected = IllegalArgumentException::class) fun negativeWriteRejected() { val p = PcmProgress(); p.begin(0,8); p.wrote(-1) }
    @Test(expected = IllegalArgumentException::class) fun overWriteRejected() { val p = PcmProgress(); p.begin(0,8); p.wrote(10) }
    @Test(expected = IllegalArgumentException::class) fun oddChunkRejected() { PcmProgress().begin(0,3) }
    @Test(expected = IllegalArgumentException::class) fun outOfOrderChunkRejected() { PcmProgress().begin(1,4) }
    @Test(expected = IllegalArgumentException::class) fun duplicateChunkRejected() { val p = PcmProgress(); p.begin(0,4); p.wrote(4); p.begin(0,4) }
    @Test(expected = IllegalArgumentException::class) fun oversizedChunkRejected() { PcmProgress().begin(0,16386) }
}

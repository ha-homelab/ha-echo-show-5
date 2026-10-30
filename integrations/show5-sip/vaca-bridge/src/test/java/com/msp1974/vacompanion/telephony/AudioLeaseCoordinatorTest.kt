package com.msp1974.vacompanion.telephony

import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.async
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield
import org.junit.Assert.*
import org.junit.Test

class AudioLeaseCoordinatorTest {
    private val token = "11111111-2222-3333-4444-555555555555"
    private val other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    private class Fixture {
        var time = 100L
        var journal: AudioLeaseCoordinator.Record? = null
        var busy = false
        var muted = false
        var stopped = false
        var stopCount = 0
        var resumed = 0
        var failStop = false
        var failResume = false
        var failPersist = false
        var failClear = false
        var barrier: CompletableDeferred<Unit>? = null
        fun machine(initial: AudioLeaseCoordinator.Record? = null) = AudioLeaseCoordinator(initial,
            now = { time }, persist = { if (failPersist || (it == null && failClear)) error("disk"); journal = it },
            canAcquire = { !busy }, snapshotMuted = { muted },
            prepare = { barrier?.await(); if (failStop) error("native stop"); stopped = true; stopCount++ },
            resume = { if (failResume) error("restart"); resumed++ })
    }

    @Test fun grantWaitsForActualStop() = runBlocking {
        val f = Fixture(); f.barrier = CompletableDeferred(); val m = f.machine()
        val grant = async { m.acquire(42, token, 30_000, 3) }; yield()
        assertFalse(grant.isCompleted); assertTrue(m.inhibited); assertNotNull(f.journal)
        f.barrier!!.complete(Unit)
        assertTrue(grant.await().ok); assertTrue(f.stopped); assertEquals("held", f.journal!!.phase)
    }

    @Test fun preservesInitiallyMutedChoiceAndDoesNotOverwriteLaterChoice() = runBlocking {
        val f = Fixture(); f.muted = true; val m = f.machine()
        assertTrue(m.acquire(42, token, 30_000, 3).ok); assertTrue(f.journal!!.priorMuted)
        f.muted = false
        assertTrue(m.release(42, token).ok); assertFalse(f.muted); assertFalse(m.inhibited)
        assertNull(f.journal); assertEquals(1, f.resumed)
    }

    @Test fun rejectsBusyVoiceWithoutStoppingOrMuting() = runBlocking {
        val f = Fixture(); f.busy = true; val m = f.machine()
        assertFalse(m.acquire(42, token, 30_000, 3).ok)
        assertFalse(f.stopped); assertFalse(m.inhibited); assertNull(f.journal)
    }

    @Test fun secondOwnerAndStaleTokenCannotRelease() = runBlocking {
        val f = Fixture(); val m = f.machine(); m.acquire(42, token, 30_000, 3)
        assertFalse(m.acquire(43, other, 30_000, 3).ok)
        assertFalse(m.release(43, token).ok); assertFalse(m.release(42, other).ok)
        assertTrue(m.inhibited); assertEquals(0, f.resumed)
        assertEquals("", m.status(43).token); assertEquals(token, m.status(42).token)
    }

    @Test fun nativeStopFailureNeverGrantsAndRetainsRecoverableOwnership() = runBlocking {
        val f = Fixture(); f.failStop = true; val m = f.machine()
        assertFalse(m.acquire(42, token, 30_000, 3).ok)
        assertTrue(m.inhibited); assertEquals("recovery", f.journal!!.phase)
        f.failStop = false; assertTrue(m.release(42, token).ok)
    }

    @Test fun persistenceFailureNeverGrants() = runBlocking {
        val f = Fixture(); f.failPersist = true; val m = f.machine()
        assertFalse(m.acquire(42, token, 30_000, 3).ok); assertFalse(f.stopped)
        assertTrue(m.inhibited)
    }

    @Test fun expiryRevokesButCannotResumeWhileClientMayCapture() = runBlocking {
        val f = Fixture(); val m = f.machine(); m.acquire(42, token, 10_000, 3)
        f.time += 10_000
        assertEquals(token, m.expire()!!.token); assertTrue(m.inhibited)
        assertEquals(0, f.resumed); assertNull(m.expire())
        assertFalse(m.renew(42, token, 30_000).ok)
        assertTrue(m.release(42, token).ok)
    }

    @Test fun freshRenewalPreventsOldDeadlineFromRevoking() = runBlocking {
        val f = Fixture(); val m = f.machine(); m.acquire(42, token, 10_000, 3)
        f.time += 5_000; assertTrue(m.renew(42, token, 30_000).ok)
        f.time += 5_000; assertNull(m.expire()); assertTrue(m.inhibited)
    }

    @Test fun processRestartRemainsInhibitedUntilMatchingRelease() = runBlocking {
        val f = Fixture(); val old = f.machine(); old.acquire(42, token, 30_000, 3)
        val m = f.machine(f.journal!!.copy(phase = "recovery"))
        assertTrue(m.inhibited); assertFalse(m.acquire(42, other, 30_000, 3).ok)
        assertTrue(m.release(42, token).ok); assertFalse(m.inhibited)
    }

    @Test fun repeatedReleaseIsIdempotentAndCannotEndNewCall() = runBlocking {
        val f = Fixture(); val m = f.machine(); m.acquire(42, token, 30_000, 3)
        assertTrue(m.release(42, token).ok); assertTrue(m.release(42, token).ok)
        assertEquals(1, f.resumed)
        assertTrue(m.acquire(42, other, 30_000, 3).ok)
        assertFalse(m.release(42, token).ok); assertTrue(m.inhibited)
    }

    @Test fun failedRestorationRetainsJournalAndCanRetry() = runBlocking {
        val f = Fixture(); val m = f.machine(); m.acquire(42, token, 30_000, 3)
        f.failResume = true; assertFalse(m.release(42, token).ok)
        assertTrue(m.inhibited); assertNotNull(f.journal)
        f.failResume = false; assertTrue(m.release(42, token).ok); assertNull(f.journal)
    }

    @Test fun failedJournalClearClosesAlreadyRestartedCapture() = runBlocking {
        val f = Fixture(); val m = f.machine(); m.acquire(42, token, 30_000, 3)
        f.failClear = true
        assertFalse(m.release(42, token).ok)
        assertEquals(1, f.resumed); assertEquals(2, f.stopCount)
        assertTrue(m.inhibited); assertNotNull(f.journal)
    }

    @Test fun invalidDurationsAndTokensCannotAcquire() = runBlocking {
        val f = Fixture(); val m = f.machine()
        for ((id, duration) in listOf("short" to 30_000L, token to 9999L, token to 60001L)) {
            try { m.acquire(42, id, duration, 3); fail("accepted invalid lease") }
            catch (_: IllegalArgumentException) { }
        }
        assertFalse(m.inhibited); assertNull(f.journal)
    }
}

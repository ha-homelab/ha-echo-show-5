package com.msp1974.vacompanion.feedback

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class WakeCueOwnershipTest {
    @Test fun aPooledPlayersOldGenerationCannotCompleteItsNextPlay() {
        val ownership = WakeCueOwnership()
        val player = Any()
        val old = ownership.begin(player)
        val current = ownership.begin(player)
        assertTrue(current > old)
        assertFalse(ownership.isCurrent(player, old))
        assertFalse(ownership.release(player, old))
        assertTrue(ownership.isCurrent(player, current))
        assertEquals(current, ownership.generation)
    }

    @Test fun equalButDistinctPlayersDoNotOwnEachOthersCue() {
        data class Player(val name: String)
        val ownership = WakeCueOwnership()
        val player = Player("same")
        val token = ownership.begin(player)
        assertFalse(ownership.isCurrent(Player("same"), token))
        assertFalse(ownership.release(Player("same"), token))
        assertTrue(ownership.isCurrent(player, token))
    }

    @Test fun invalidationRejectsAQueuedCallbackAndDoesNotPoisonNextPlay() {
        val ownership = WakeCueOwnership()
        val player = Any()
        val old = ownership.begin(player)
        ownership.invalidate()
        assertFalse(ownership.isCurrent(player, old))
        val next = ownership.begin(player)
        assertFalse(ownership.release(player, old))
        assertTrue(ownership.isCurrent(player, next))
    }

    @Test fun anotherPlayersLaterCueSurvivesOldCompletion() {
        val ownership = WakeCueOwnership()
        val oldPlayer = Any()
        val nextPlayer = Any()
        val old = ownership.begin(oldPlayer)
        val next = ownership.begin(nextPlayer)
        assertFalse(ownership.release(oldPlayer, old))
        assertTrue(ownership.isCurrent(nextPlayer, next))
        assertTrue(ownership.release(nextPlayer, next))
        assertFalse(ownership.isCurrent(nextPlayer, next))
        assertFalse(ownership.release(nextPlayer, next))
    }

    @Test fun supersededFailureCannotExecuteAnyCompletionSideEffects() {
        val ownership = WakeCueOwnership()
        val player = Any()
        val old = ownership.begin(player)
        val next = ownership.begin(player)
        var failureCalls = 0
        assertFalse(ownership.release(player, old) { failureCalls++ })
        assertEquals(0, failureCalls)
        assertTrue(ownership.isCurrent(player, next))
        ownership.invalidate()
        assertFalse(ownership.release(player, next) { failureCalls++ })
        assertEquals(0, failureCalls)
    }

    @Test fun currentFailureRunsExactlyOnceWhileItsOwnershipIsStillActive() {
        val ownership = WakeCueOwnership()
        val player = Any()
        val token = ownership.begin(player)
        var failureCalls = 0
        assertTrue(ownership.release(player, token) {
            assertTrue(ownership.isCurrent(player, token))
            failureCalls++
        })
        assertFalse(ownership.release(player, token) { failureCalls++ })
        assertEquals(1, failureCalls)
        assertFalse(ownership.isCurrent(player, token))
    }

    @Test fun throwingCompletionStillReleasesItsToken() {
        val ownership = WakeCueOwnership()
        val player = Any()
        val token = ownership.begin(player)
        val expected = IllegalStateException("completion failure")
        var caught: Throwable? = null
        try {
            ownership.release(player, token) { throw expected }
        } catch (error: IllegalStateException) {
            caught = error
        }
        assertTrue(caught === expected)
        assertFalse(ownership.isCurrent(player, token))
        assertFalse(ownership.release(player, token))
    }

    @Test fun reentrantAdmissionSurvivesOldCompletionIncludingAnException() {
        for (throws in listOf(false, true)) {
            val ownership = WakeCueOwnership()
            val player = Any()
            val old = ownership.begin(player)
            var current = -1L
            try {
                ownership.release(player, old) {
                    current = ownership.begin(player)
                    if (throws) throw IllegalStateException("completion failure")
                }
            } catch (_: IllegalStateException) {
                assertTrue(throws)
            }
            assertTrue(current > old)
            assertTrue(ownership.isCurrent(player, current))
            assertEquals(current, ownership.generation)
            assertFalse(ownership.isCurrent(player, old))
        }
    }
}

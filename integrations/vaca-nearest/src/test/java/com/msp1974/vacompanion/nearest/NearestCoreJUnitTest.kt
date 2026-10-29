package com.msp1974.vacompanion.nearest

import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.Parameterized

/** One Gradle/JUnit result per core case, sharing the exact standalone regression assertions. */
@RunWith(Parameterized::class)
class NearestCoreJUnitTest(private val caseName: String) {
    @Test fun verifiedCoreCase() { NearestCoreTests.runCase(caseName, fixtures) }

    companion object {
        private val fixtures: Map<String, String> = checkNotNull(
            NearestCoreJUnitTest::class.java.getResourceAsStream("/nearest/golden-vectors.txt")
        ) { "Missing test resource: nearest/golden-vectors.txt" }.bufferedReader().useLines { lines ->
            lines.filter { it.isNotBlank() }.associate { it.substringBefore('=') to it.substringAfter('=') }
        }

        @JvmStatic
        @Parameterized.Parameters(name = "{0}")
        fun cases(): Collection<Array<String>> = NearestCoreTests.caseNames(fixtures).map { arrayOf(it) }
    }
}

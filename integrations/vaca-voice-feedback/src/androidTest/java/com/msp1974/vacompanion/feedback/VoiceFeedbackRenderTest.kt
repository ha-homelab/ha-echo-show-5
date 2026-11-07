package com.msp1974.vacompanion.feedback

import android.graphics.Bitmap
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.test.SemanticsMatcher
import androidx.compose.ui.test.assert
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.unit.sp
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import org.junit.Rule
import org.junit.Test

/** Synthetic drawing/semantics proof only: never starts VACA, audio, HA or detection. */
class VoiceFeedbackRenderTest {
    @get:Rule val compose = createComposeRule()

    @Test fun rendersClockAndAcceptedPhasesWithoutAudio() {
        val owner = Any()
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val directory = File(context.cacheDir, "voice-feedback-check").apply { mkdirs() }
        val manifest = StringBuilder("Synthetic Compose rendering; no acoustic wake or audio test.\n")
        VoiceFeedbackRuntime.clearAll()
        compose.mainClock.autoAdvance = false
        try {
            compose.setContent { ClockFixture() }
            compose.mainClock.advanceTimeBy(64)
            compose.waitForIdle()
            compose.onNodeWithTag("clock-time").assertIsDisplayed()
            compose.onNodeWithTag("voice-feedback").assertDoesNotExist()

            compose.runOnIdle { VoiceFeedbackRuntime.begin(owner) }
            checkAndSave("Listening", "listening", directory, manifest)
            compose.runOnIdle { VoiceFeedbackRuntime.update(owner, "AWAITING_RESPONSE") }
            checkAndSave("Thinking", "thinking", directory, manifest)
            compose.runOnIdle { VoiceFeedbackRuntime.update(owner, "STREAMING_TTS") }
            checkAndSave("Speaking", "speaking", directory, manifest)
            compose.runOnIdle { VoiceFeedbackRuntime.clear(owner) }
            compose.mainClock.advanceTimeBy(32)
            compose.waitForIdle()
            compose.onNodeWithTag("voice-feedback").assertDoesNotExist()
            compose.onNodeWithTag("clock-time").assertIsDisplayed()
            save("idle", directory, manifest)
            File(directory, "dimensions.txt").writeText(manifest.toString())
        } finally {
            compose.runOnIdle { VoiceFeedbackRuntime.clearAll() }
        }
    }

    private fun checkAndSave(label: String, filename: String, directory: File, manifest: StringBuilder) {
        compose.mainClock.advanceTimeBy(640)
        compose.waitForIdle()
        compose.onNodeWithTag("voice-feedback").assertIsDisplayed()
            .assert(SemanticsMatcher.expectValue(SemanticsProperties.StateDescription, label))
        save(filename, directory, manifest)
    }

    private fun save(name: String, directory: File, manifest: StringBuilder) {
        // Read the composed screen, including retained sibling layers. A node-only
        // capture can omit the clock's cached layer when the overlay is absent.
        val bitmap = checkNotNull(InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot())
        File(directory, "$name.png").outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        manifest.append("$name.png ${bitmap.width}x${bitmap.height}\n")
    }

    @Composable
    private fun ClockFixture() {
        Box(Modifier.fillMaxSize().background(Color(0xFF050608)).testTag("feedback-fixture")) {
            Column(Modifier.align(Alignment.Center), horizontalAlignment = Alignment.CenterHorizontally) {
                Text("10:24", color = Color(0xFFF5F6F8), fontSize = 96.sp,
                    modifier = Modifier.testTag("clock-time"))
                Text("Saturday, November 7", color = Color(0xFF9299A5), fontSize = 18.sp)
            }
            VoiceFeedbackOverlay()
        }
    }
}

package com.msp1974.vacompanion.audio

import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.msp1974.vacompanion.wakeword.openwakeword.ExactWakeConfig
import com.msp1974.vacompanion.wakeword.openwakeword.audio.ExactOnnxFrontend
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.abs

/** Explicit private-fixture replay; does not open a microphone or play audio. */
@RunWith(AndroidJUnit4::class)
class FrameMicrophoneReplayTest {
    @Test fun privatePcmMatchesReferenceAndClassifierDecisions() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val directory = File(context.filesDir, "leveler-check")
        val manifest = JSONObject(File(directory, "fixture.json").readText())
        fun pcm(name: String): ShortArray {
            require(name.matches(Regex("[0-9]+\\.(pcm|leveled)")))
            val input = ByteBuffer.wrap(File(directory, name).readBytes())
                .order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
            return ShortArray(input.remaining()).also { input.get(it) }
        }
        val assets = checkNotNull(ExactWakeConfig.load(
            File(context.filesDir, "custom/wakewords/openwakeword"), listOf(manifest.getString("model_id"))))
        val threshold = manifest.getDouble("threshold")
        val env = OrtEnvironment.getEnvironment()
        val results = JSONArray()
        OrtSession.SessionOptions().use { options ->
            options.setIntraOpNumThreads(1); options.setInterOpNumThreads(1)
            env.createSession(assets.classifier.absolutePath, options).use { classifier ->
                val cases = manifest.getJSONArray("cases")
                for (i in 0 until cases.length()) {
                    val row = cases.getJSONObject(i)
                    val input = pcm(row.getString("pcm"))
                    val expected = pcm(row.getString("leveled"))
                    val leveler = FrameMicrophoneLeveler()
                    var written = 0; var offset = 0; var part = 0; var pcmDelta = 0
                    var maxScore = 0f; var windows = 0
                    val started = System.nanoTime()
                    ExactOnnxFrontend(assets.mel, assets.embedding).use { frontend ->
                        val chunks = intArrayOf(1, 127, 512, 1280, 2048, 2567, 83)
                        while (offset < input.size) {
                            val end = minOf(input.size, offset + chunks[part++ % chunks.size])
                            val output = leveler.process(input.copyOfRange(offset, end))
                            for (sample in output) {
                                pcmDelta = maxOf(pcmDelta, abs(sample.toInt() - expected[written++].toInt()))
                            }
                            for (features in frontend.process(output)) {
                                OnnxTensor.createTensor(env, features).use { tensor ->
                                    classifier.run(mapOf(classifier.inputNames.first() to tensor)).use { scores ->
                                        maxScore = maxOf(maxScore, (scores[0] as OnnxTensor).floatBuffer.get(0))
                                        windows++
                                    }
                                }
                            }
                            offset = end
                        }
                    }
                    var previousMax = 0f
                    val previous = AutomaticGainController(16000)
                    ExactOnnxFrontend(assets.mel, assets.embedding).use { frontend ->
                        var start = 0
                        while (start < input.size) {
                            val end = minOf(input.size, start + 1280)
                            for (features in frontend.process(previous.process(input.copyOfRange(start, end)))) {
                                OnnxTensor.createTensor(env, features).use { tensor ->
                                    classifier.run(mapOf(classifier.inputNames.first() to tensor)).use { scores ->
                                        previousMax = maxOf(previousMax, (scores[0] as OnnxTensor).floatBuffer.get(0))
                                    }
                                }
                            }
                            start = end
                        }
                    }
                    assertEquals(expected.size, written)
                    assertTrue("PCM delta case $i: $pcmDelta", pcmDelta <= 1)
                    assertEquals("Score parity case $i", row.getDouble("expected_max"), maxScore.toDouble(), 0.002)
                    assertEquals("Wake decision case $i", row.getInt("label") == 1, maxScore >= threshold)
                    results.put(JSONObject().put("case", i).put("positive", row.getInt("label") == 1)
                        .put("previous_max_score", previousMax.toDouble()).put("pcm_max_delta", pcmDelta).put("windows", windows).put("max_score", maxScore.toDouble())
                        .put("elapsed_ms", (System.nanoTime() - started) / 1_000_000))
                }
            }
        }
        File(directory, "android-results.json").writeText(results.toString(2))
    }
}

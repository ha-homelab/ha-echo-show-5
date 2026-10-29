package com.msp1974.vacompanion.nearest

import android.content.Context
import android.util.AtomicFile
import org.json.JSONObject
import java.io.File
import java.util.concurrent.CopyOnWriteArraySet

/** The house word is deliberately not a HA setting, intent extra, log or data-class string. */
class NearestConfig(
    val enabled: Boolean = false, val name: String = "", internal val houseWord: String = "",
    val windowMs: Long = 300, val offsetDb: Double = 0.0, val port: Int = 18127,
) {
    // Explicit comparison avoids data-class toString() exposing the house credential.
    internal fun sameConfiguration(other: NearestConfig) =
        enabled == other.enabled && name == other.name && houseWord == other.houseWord &&
            windowMs == other.windowMs && offsetDb == other.offsetDb && port == other.port

    fun validate() {
        require(name.length <= 40 && name.none { it.isISOControl() })
        require(windowMs in 100L..500L && offsetDb.isFinite() && offsetDb in -30.0..30.0)
        require(port in 1024..65535)
        require(houseWord.length <= 256 && houseWord.none { it.isISOControl() })
        // Native TECHO5 permits a nonempty legacy House word; importing it must not
        // silently disable coordination or rotate the rest of the household.
        if (enabled) require(name.isNotBlank() && houseWord.isNotEmpty())
    }
    companion object {
        /** Blank preserves an imported word; newly entered words use the stronger minimum. */
        internal fun houseWordFromInput(input: String, saved: String): String {
            if (input.isEmpty()) return saved
            require(input.length >= 16)
            return input
        }
    }
}

object NearestSettings {
    private val listeners = CopyOnWriteArraySet<() -> Unit>()
    private fun file(context: Context) = AtomicFile(File(context.filesDir, "nearest-device.json"))
    fun read(context: Context): NearestConfig {
        val f = file(context)
        if (!f.baseFile.exists()) return NearestConfig()
        return try {
            require(f.baseFile.length() in 1..4096 && !java.nio.file.Files.isSymbolicLink(f.baseFile.toPath()))
            val d = f.openRead().bufferedReader().use { JSONObject(it.readText()) }
            require(d.getInt("schema") == 1)
            NearestConfig(d.optBoolean("enabled", false), d.optString("name", ""),
                d.optString("house_word", ""), d.optLong("window_ms", 300),
                d.optDouble("offset_db", 0.0), d.optInt("port", 18127)).also { it.validate() }
        } catch (_: Exception) { NearestConfig() }
    }
    fun save(context: Context, config: NearestConfig) {
        config.validate()
        val d = JSONObject().put("schema", 1).put("enabled", config.enabled).put("name", config.name)
            .put("house_word", config.houseWord).put("window_ms", config.windowMs)
            .put("offset_db", config.offsetDb).put("port", config.port)
        val f = file(context); val stream = f.startWrite()
        try { stream.write(d.toString().toByteArray(Charsets.UTF_8)); f.finishWrite(stream) }
        catch (e: Exception) { f.failWrite(stream); throw e }
        f.baseFile.setReadable(false, false); f.baseFile.setWritable(false, false)
        check(f.baseFile.setReadable(true, true) && f.baseFile.setWritable(true, true))
        listeners.forEach { it() }
    }
    fun listen(listener: () -> Unit) { listeners.add(listener) }
    fun unlisten(listener: () -> Unit) { listeners.remove(listener) }
}

#!/usr/bin/env python3
"""Exercise the patched production dispatch methods with a manually queued Main dispatcher.

The Kotlin method bodies are extracted from the supplied patched VACA source,
not copied test implementations. Android/player dependencies are explicit fakes;
no device, network, audio or Home Assistant access is performed.
"""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile


def method(text, name):
    start = text.index("    private suspend fun " + name + "(")
    body = text.index("{", start)
    depth = 1
    end = body + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end].replace("private suspend fun", "suspend fun", 1).replace("Dispatchers.Main", "main")


SUPPORT = r'''
import java.io.File
import kotlin.coroutines.CoroutineContext
import kotlinx.coroutines.*
object AudioLeaseRuntime { var inhibited = false }
class QueuedMain : CoroutineDispatcher() {
    private val pending = ArrayDeque<Runnable>()
    override fun dispatch(context: CoroutineContext, block: Runnable) { pending.add(block) }
    fun drain() { while (pending.isNotEmpty()) pending.removeFirst().run() }
}
class FakeJson {
    val jsonObject: Map<String, FakeJson> = emptyMap()
    val jsonPrimitive get() = this
    val contentOrNull: String? = null
    val floatOrNull: Float? = null
}
object Json { fun parseToJsonElement(value: String) = FakeJson() }
class Player {
    var starts = 0; var stops = 0
    fun play(url: String, volume: Float) { starts++ }
    fun start(uri: String) { starts++ }
    fun resume() { starts++ }
    fun stop() { stops++ }
    fun pause() { stops++ }
    fun setVolume(volume: Float) {}
}
class Media { val musicPlayer = Player(); val alarmPlayer = Player() }
data class Alarm(val id: String, val custom: Boolean, val filename: String)
class Events { fun notifyEvent(event: Event) {} }
class Event(val name: String, val before: String, val after: String)
class Config { val alarmSound = "default"; val availableAlarms = emptyList<Alarm>(); val eventBroadcaster = Events() }
class Context { val filesDir = File("/unused") }
object CustomFileDownloader { const val CUSTOM_DIR = "custom"; const val ALARMS_DIR = "alarms" }
fun String.toUri() = this
fun File.toUri() = toString()
class Subject(val main: CoroutineDispatcher) {
    val mediaManager = Media(); val config = Config(); val context = Context()
    fun sendSetting(name: String, value: Boolean) {}
'''

RUNNER = r'''
}
fun main() = runBlocking {
    suspend fun exercise(alarm: Boolean, blockAfterDispatch: Boolean, stop: Boolean = false) {
        val main = QueuedMain(); val subject = Subject(main)
        AudioLeaseRuntime.inhibited = false
        val work = async(start = CoroutineStart.UNDISPATCHED) {
            if (alarm) subject.handleAlarmAction(!stop)
            else subject.handleMediaPlayerAction(if (stop) "stop" else "play", "")
        }
        check(!work.isCompleted) { "Production method did not queue on Main" }
        AudioLeaseRuntime.inhibited = blockAfterDispatch
        main.drain(); work.await()
        val player = if (alarm) subject.mediaManager.alarmPlayer else subject.mediaManager.musicPlayer
        check(player.starts == if (stop || blockAfterDispatch) 0 else 1) {
            "Queued start crossed audio ownership: alarm=$alarm, blocked=$blockAfterDispatch"
        }
        if (stop) check(player.stops == 1) { "Stop must still work during a lease" }
    }
    exercise(false, true); exercise(true, true)
    exercise(false, false); exercise(true, false)
    exercise(false, true, true); exercise(true, true, true)
    println("Six production-method queued dispatch checks passed")
}
'''


def verify(source, compiler, coroutines):
    java = source / "app/src/main/java/com/msp1974/vacompanion"
    text = (java / "satellite/Satellite.kt").read_text()
    code = SUPPORT + method(text, "handleMediaPlayerAction") + "\n" + method(text, "handleAlarmAction") + RUNNER
    for name in ("MusicPlayerService", "AlarmService"):
        service = (java / f"players/{name}.kt").read_text()
        entry = service.index("override fun onStartCommand")
        guarded = service.index("if (AudioLeaseRuntime.inhibited)", entry)
        dispatch = service.index("        play(", entry)
        assert guarded < dispatch, f"{name} must reject delayed service delivery before playback"
        resume = service.index("    fun resume() {")
        assert service.index("if (AudioLeaseRuntime.inhibited)", resume) < service.index("player.play()", resume)
    with tempfile.TemporaryDirectory(prefix="vaca-queued-dispatch-") as directory:
        directory = Path(directory)
        kotlin = directory / "QueuedDispatch.kt"
        kotlin.write_text(code)
        jar = directory / "test.jar"
        subprocess.run([str(compiler), str(kotlin), "-nowarn", "-cp", str(coroutines), "-include-runtime", "-d", str(jar)], check=True)
        subprocess.run(["java", "-cp", f"{jar}:{coroutines}", "QueuedDispatchKt"], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--kotlinc", default=shutil.which("kotlinc"), type=Path)
    parser.add_argument("--coroutines-jar", type=Path)
    args = parser.parse_args()
    if args.kotlinc is None:
        parser.error("kotlinc is required")
    home = args.kotlinc.resolve().parent.parent
    candidates = [home / "lib/kotlinx-coroutines-core-jvm.jar", home / "libexec/lib/kotlinx-coroutines-core-jvm.jar"]
    library = args.coroutines_jar or next((p for p in candidates if p.is_file()), candidates[0])
    if not library.is_file():
        parser.error("Provide the Kotlin coroutine runtime with --coroutines-jar")
    verify(args.source.resolve(), args.kotlinc, library)

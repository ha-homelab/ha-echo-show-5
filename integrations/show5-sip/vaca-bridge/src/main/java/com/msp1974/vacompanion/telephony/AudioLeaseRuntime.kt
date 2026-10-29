package com.msp1974.vacompanion.telephony

import android.content.Context
import android.os.SystemClock
import android.provider.Settings
import android.util.AtomicFile
import com.msp1974.vacompanion.satellite.Satellite
import com.msp1974.vacompanion.wyoming.SatelliteState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import org.json.JSONObject
import java.io.File
import java.util.concurrent.CopyOnWriteArraySet

/** One process-wide capture inhibitor shared by every Satellite lifecycle. */
object AudioLeaseRuntime {
    internal val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val satellites = CopyOnWriteArraySet<Satellite>()
    private var machine: AudioLeaseCoordinator? = null
    private var invalidJournal = false
    internal var boot: Int = -1
        private set
    val inhibited: Boolean get() = invalidJournal || machine?.inhibited != false
    internal val coordinator: AudioLeaseCoordinator get() = checkNotNull(machine)

    @Synchronized fun initialize(context: Context) {
        if (machine != null) return
        boot = Settings.Global.getInt(context.contentResolver, Settings.Global.BOOT_COUNT, -1)
        val journal = AtomicFile(File(context.filesDir, "audio-lease.json"))
        var initial: AudioLeaseCoordinator.Record? = null
        if (journal.baseFile.exists() || File(journal.baseFile.path + ".bak").exists()) {
            try {
                val json = journal.openRead().bufferedReader().use { JSONObject(it.readText()) }
                require(json.getInt("version") == 1)
                val storedBoot = json.getInt("boot")
                if (boot >= 0 && storedBoot >= 0 && boot != storedBoot) {
                    // A full device reboot terminates both processes and their capture handles.
                    journal.delete()
                } else {
                    initial = AudioLeaseCoordinator.Record(json.getInt("uid"), json.getString("token"),
                        json.getBoolean("prior_muted"), json.getLong("deadline"), storedBoot, "recovery")
                    require(initial.token.matches(Regex("[A-Za-z0-9_-]{16,80}")))
                }
            } catch (_: Exception) {
                // Never resume capture based on an unreadable ownership journal.
                invalidJournal = true
            }
        }
        machine = AudioLeaseCoordinator(initial, SystemClock::elapsedRealtime,
            persist = { record ->
                check(!invalidJournal) { "Invalid audio ownership journal" }
                if (record == null) {
                    journal.delete()
                    check(!journal.baseFile.exists() && !File(journal.baseFile.path + ".bak").exists())
                }
                else {
                    val data = JSONObject().put("version", 1).put("uid", record.uid)
                        .put("token", record.token).put("prior_muted", record.priorMuted)
                        .put("deadline", record.deadline).put("boot", record.boot)
                        .put("phase", record.phase).toString().toByteArray(Charsets.UTF_8)
                    val stream = journal.startWrite()
                    try { stream.write(data); journal.finishWrite(stream) }
                    catch (e: Exception) { journal.failWrite(stream); throw e }
                }
            },
            canAcquire = { !invalidJournal && satellites.none { it.isBusyForAudioLease() } },
            snapshotMuted = { satellites.firstOrNull()?.config?.isMuted ?: true },
            prepare = { satellites.forEach { it.pauseForAudioLease() } },
            resume = {
                satellites.filter { it.state == SatelliteState.RUNNING }.forEach { it.resumeAfterAudioLease() }
            })
    }

    fun attach(satellite: Satellite) { satellites.add(satellite) }
    fun detach(satellite: Satellite) { satellites.remove(satellite) }
    internal fun journalValid() = !invalidJournal
}
